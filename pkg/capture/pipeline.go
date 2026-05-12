package capture

import (
	"bufio"
	"context"
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

type Pipeline struct {
	cfg      Config
	reporter Reporter
	health   *healthStore
}

func NewPipeline(cfg Config, reporter Reporter) (*Pipeline, error) {
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	if reporter == nil {
		reporter = NopReporter{}
	}
	p := &Pipeline{
		cfg:      cfg,
		reporter: reporter,
		health:   &healthStore{},
	}
	p.health.update(func(s *HealthSnapshot) {
		s.State = StateStarting
	})
	return p, nil
}

func (p *Pipeline) Snapshot() HealthSnapshot {
	return p.health.snapshot()
}

func (p *Pipeline) Run(ctx context.Context) error {
	if err := os.MkdirAll(p.cfg.OutputDir, 0o755); err != nil {
		return fmt.Errorf("create output dir: %w", err)
	}

	orphaned, err := recoverOrphanedSegments(p.cfg.OutputDir)
	if err != nil {
		return err
	}
	for _, path := range orphaned {
		p.emitEvent(ctx, EventSegmentOrphaned, map[string]string{"path": path})
		p.metric(ctx, MetricSegmentsOrphan, 1)
		p.health.update(func(s *HealthSnapshot) {
			s.SegmentsOrphaned++
		})
	}

	p.status(ctx, StateRunning, "capture pipeline started")
	p.emitEvent(ctx, EventCaptureStarted, map[string]string{"camera_id": p.cfg.CameraID})

	for {
		err := p.runOneEncoderSession(ctx)
		if err == nil || errors.Is(err, context.Canceled) {
			p.status(ctx, StateStopped, "capture pipeline stopped")
			p.emitEvent(ctx, EventCaptureStopped, map[string]string{"camera_id": p.cfg.CameraID})
			return nil
		}

		p.health.update(func(s *HealthSnapshot) {
			s.EncoderRestarts++
			s.LastError = err.Error()
		})
		p.status(ctx, StateDegraded, "encoder session ended unexpectedly")
		p.emitEvent(ctx, EventEncoderRestarting, map[string]string{"error": err.Error()})
		p.metric(ctx, MetricEncoderRestarts, 1)

		if p.cfg.RestartBackoff > 0 {
			select {
			case <-ctx.Done():
				return nil
			case <-time.After(p.cfg.RestartBackoff):
			}
		}
	}
}

func (p *Pipeline) runOneEncoderSession(ctx context.Context) error {
	segmentStart := p.cfg.SegmentStartNumber(time.Now())
	args := buildFFmpegArgs(p.cfg, segmentStart)

	cmd := exec.Command(p.cfg.FFmpegBinary, args...)
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("ffmpeg stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start ffmpeg: %w", err)
	}

	watchCtx, cancelWatch := context.WithCancel(ctx)
	defer cancelWatch()

	var wg sync.WaitGroup
	wg.Add(3)
	go func() {
		defer wg.Done()
		p.consumeStderr(watchCtx, stderr)
	}()
	go func() {
		defer wg.Done()
		p.watchSegmentList(watchCtx, p.cfg.SegmentListPath())
	}()
	go func() {
		defer wg.Done()
		p.watchNewPartialSegments(watchCtx)
	}()

	waitCh := make(chan error, 1)
	go func() {
		waitCh <- cmd.Wait()
	}()

	select {
	case <-ctx.Done():
		_ = gracefulStop(cmd.Process)
		cancelWatch()
		wg.Wait()
		<-waitCh
		return context.Canceled
	case err := <-waitCh:
		cancelWatch()
		wg.Wait()
		if err != nil {
			return fmt.Errorf("ffmpeg exited: %w", err)
		}
		return nil
	}
}

func (p *Pipeline) consumeStderr(ctx context.Context, r io.Reader) {
	s := bufio.NewScanner(r)
	s.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for s.Scan() {
		line := strings.TrimSpace(s.Text())
		if line == "" {
			continue
		}
		if strings.Contains(line, "frame=") {
			p.health.update(func(s *HealthSnapshot) {
				s.LastHeartbeat = time.Now().UTC()
			})
		}
		if strings.Contains(strings.ToLower(line), "error") {
			p.emitEvent(ctx, EventCaptureError, map[string]string{"stderr": line})
			p.health.update(func(s *HealthSnapshot) {
				s.LastError = line
			})
		}
		select {
		case <-ctx.Done():
			return
		default:
		}
	}
}

func (p *Pipeline) watchSegmentList(ctx context.Context, path string) {
	seen := map[string]struct{}{}
	ticker := time.NewTicker(750 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			records, err := readSegmentList(path)
			if err != nil {
				continue
			}
			for _, rec := range records {
				if _, ok := seen[rec.Filename]; ok {
					continue
				}
				seen[rec.Filename] = struct{}{}
				path := rec.Filename
				if !filepath.IsAbs(path) {
					path = filepath.Join(p.cfg.OutputDir, path)
				}
				final, err := finalizeSegment(path)
				if err != nil {
					p.emitEvent(ctx, EventCaptureError, map[string]string{"error": err.Error(), "segment": path})
					continue
				}
				p.health.update(func(s *HealthSnapshot) {
					s.SegmentsFinalized++
					s.LastSegmentFinalized = time.Now().UTC()
				})
				p.metric(ctx, MetricSegmentsFinal, 1)
				p.emitEvent(ctx, EventSegmentFinalized, map[string]string{
					"path":       final,
					"start_secs": fmt.Sprintf("%.3f", rec.StartSeconds),
					"end_secs":   fmt.Sprintf("%.3f", rec.EndSeconds),
				})
			}
		}
	}
}

func (p *Pipeline) watchNewPartialSegments(ctx context.Context) {
	seen := map[string]struct{}{}
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			files, err := filepath.Glob(filepath.Join(p.cfg.OutputDir, p.cfg.CameraID+"_*.mp4.partial"))
			if err != nil {
				continue
			}
			for _, f := range files {
				if _, ok := seen[f]; ok {
					continue
				}
				seen[f] = struct{}{}
				p.health.update(func(s *HealthSnapshot) {
					s.LastSegmentStarted = time.Now().UTC()
				})
				p.emitEvent(ctx, EventSegmentStarted, map[string]string{"path": f})
			}
		}
	}
}

type segmentListRecord struct {
	Filename     string
	StartSeconds float64
	EndSeconds   float64
}

func readSegmentList(path string) ([]segmentListRecord, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.FieldsPerRecord = -1

	var out []segmentListRecord
	for {
		rec, err := r.Read()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, err
		}
		if len(rec) < 3 {
			continue
		}
		start, err := strconv.ParseFloat(rec[1], 64)
		if err != nil {
			continue
		}
		end, err := strconv.ParseFloat(rec[2], 64)
		if err != nil {
			continue
		}
		out = append(out, segmentListRecord{
			Filename:     rec[0],
			StartSeconds: start,
			EndSeconds:   end,
		})
	}
	return out, nil
}

func finalizeSegment(path string) (string, error) {
	if !strings.HasSuffix(path, ".partial") {
		return path, nil
	}
	final := strings.TrimSuffix(path, ".partial")
	if _, err := os.Stat(path); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return final, nil
		}
		return "", err
	}
	if err := os.Rename(path, final); err != nil {
		return "", err
	}
	return final, nil
}

func recoverOrphanedSegments(dir string) ([]string, error) {
	paths, err := filepath.Glob(filepath.Join(dir, "*.partial"))
	if err != nil {
		return nil, err
	}
	var orphaned []string
	for _, p := range paths {
		orphan := p + ".orphaned"
		if err := os.Rename(p, orphan); err != nil {
			return nil, fmt.Errorf("recover orphan %s: %w", p, err)
		}
		orphaned = append(orphaned, orphan)
	}
	return orphaned, nil
}

func gracefulStop(process *os.Process) error {
	if process == nil {
		return nil
	}
	if err := process.Signal(syscall.SIGINT); err != nil {
		_ = process.Kill()
		return err
	}
	time.Sleep(2 * time.Second)
	return process.Kill()
}

func (p *Pipeline) status(ctx context.Context, state ServiceState, msg string) {
	p.health.update(func(s *HealthSnapshot) {
		s.State = state
	})
	p.reporter.ReportStatus(ctx, Status{State: state, Timestamp: time.Now().UTC(), Message: msg})
}

func (p *Pipeline) metric(ctx context.Context, name string, value float64) {
	p.reporter.ReportMetric(ctx, Metric{
		Name:      name,
		Value:     value,
		Timestamp: time.Now().UTC(),
		Labels:    map[string]string{"camera_id": p.cfg.CameraID},
	})
}

func (p *Pipeline) emitEvent(ctx context.Context, name string, fields map[string]string) {
	p.reporter.ReportEvent(ctx, Event{
		Name:      name,
		Timestamp: time.Now().UTC(),
		Fields:    fields,
	})
}
