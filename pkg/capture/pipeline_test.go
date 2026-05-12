package capture

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestConfigValidateRequiresV1ResolutionAndFPS(t *testing.T) {
	cfg := DefaultConfig()
	cfg.Width = 1920
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected validation error for width")
	}

	cfg = DefaultConfig()
	cfg.FPS = 25
	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected validation error for fps")
	}
}

func TestSegmentStartNumber(t *testing.T) {
	cfg := DefaultConfig()
	cfg.SegmentSeconds = 60
	n := cfg.SegmentStartNumber(time.Unix(120, 0))
	if n != 2 {
		t.Fatalf("expected 2, got %d", n)
	}
}

func TestBuildFFmpegArgs(t *testing.T) {
	cfg := DefaultConfig()
	cfg.OutputDir = "/tmp/capture"
	args := buildFFmpegArgs(cfg, 42)
	joined := strings.Join(args, " ")
	checks := []string{
		"-f v4l2",
		"-video_size 1280x720",
		"-framerate 30",
		"-segment_time 60",
		"-segment_list /tmp/capture/front_segments.csv",
		"-segment_start_number 42",
		"/tmp/capture/front_%010d.mp4.partial",
	}
	for _, want := range checks {
		if !strings.Contains(joined, want) {
			t.Fatalf("args missing %q\n%s", want, joined)
		}
	}
}

func TestFinalizeSegmentRenamesPartial(t *testing.T) {
	dir := t.TempDir()
	partial := filepath.Join(dir, "front_0000000001.mp4.partial")
	if err := os.WriteFile(partial, []byte("test"), 0o644); err != nil {
		t.Fatalf("write partial: %v", err)
	}

	final, err := finalizeSegment(partial)
	if err != nil {
		t.Fatalf("finalize: %v", err)
	}
	if strings.HasSuffix(final, ".partial") {
		t.Fatalf("expected partial suffix removed")
	}
	if _, err := os.Stat(final); err != nil {
		t.Fatalf("final file missing: %v", err)
	}
}

func TestRecoverOrphanedSegments(t *testing.T) {
	dir := t.TempDir()
	p1 := filepath.Join(dir, "a.partial")
	p2 := filepath.Join(dir, "b.partial")
	_ = os.WriteFile(p1, []byte("x"), 0o644)
	_ = os.WriteFile(p2, []byte("y"), 0o644)

	orphaned, err := recoverOrphanedSegments(dir)
	if err != nil {
		t.Fatalf("recover: %v", err)
	}
	if len(orphaned) != 2 {
		t.Fatalf("expected 2 orphaned files, got %d", len(orphaned))
	}
	for _, p := range orphaned {
		if !strings.HasSuffix(p, ".orphaned") {
			t.Fatalf("expected orphaned suffix: %s", p)
		}
		if _, err := os.Stat(p); err != nil {
			t.Fatalf("orphaned file missing: %v", err)
		}
	}
}

func TestReadSegmentList(t *testing.T) {
	dir := t.TempDir()
	csvPath := filepath.Join(dir, "segments.csv")
	data := "front_0000000001.mp4.partial,0.000,60.005\nfront_0000000002.mp4.partial,60.005,120.020\n"
	if err := os.WriteFile(csvPath, []byte(data), 0o644); err != nil {
		t.Fatalf("write csv: %v", err)
	}

	recs, err := readSegmentList(csvPath)
	if err != nil {
		t.Fatalf("read segment list: %v", err)
	}
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	if recs[0].StartSeconds != 0 || recs[1].EndSeconds <= 120 {
		t.Fatalf("unexpected segment timing parse: %+v", recs)
	}
}
