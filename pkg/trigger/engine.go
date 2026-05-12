package trigger

import (
	"context"
	"fmt"
	"math"
	"time"
)

// Engine detects impacts and asks storage to lock related footage.
type Engine struct {
	cfg        Config
	sensor     Sensor
	storage    StorageLocker
	now        func() time.Time
	smoothedG  float64
	prevSmooth float64
	hitCount   int
	lastEvent  time.Time
	eventSeq   uint64
}

func NewEngine(cfg Config, sensor Sensor, storage StorageLocker) *Engine {
	return &Engine{
		cfg:     cfg.withDefaults(),
		sensor:  sensor,
		storage: storage,
		now:     time.Now,
	}
}

func (e *Engine) Run(ctx context.Context) error {
	samples, errs := e.sensor.Stream(ctx)
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case err := <-errs:
			if err != nil {
				return err
			}
		case s, ok := <-samples:
			if !ok {
				return nil
			}
			if err := e.processSample(ctx, s); err != nil {
				return err
			}
		}
	}
}

func (e *Engine) processSample(ctx context.Context, s Sample) error {
	t := s.Timestamp
	if t.IsZero() {
		t = e.now()
	}

	g := magnitudeG(s)
	e.smoothedG = e.cfg.SmoothingAlpha*g + (1-e.cfg.SmoothingAlpha)*e.smoothedG
	jerk := math.Abs(e.smoothedG - e.prevSmooth)
	e.prevSmooth = e.smoothedG

	if e.smoothedG >= e.cfg.ThresholdG && jerk >= e.cfg.MinJerkG {
		e.hitCount++
	} else {
		e.hitCount = 0
	}

	if e.hitCount < e.cfg.MinConsecutiveHits {
		return nil
	}
	if !e.lastEvent.IsZero() && t.Sub(e.lastEvent) < e.cfg.Cooldown {
		return nil
	}

	e.lastEvent = t
	e.eventSeq++
	req := LockRequest{
		EventID:     fmt.Sprintf("impact-%d", e.eventSeq),
		TriggeredAt: t,
		PreWindow:   e.cfg.PreWindow,
		PostWindow:  e.cfg.PostWindow,
		Reason:      "g-sensor-impact",
		PeakG:       e.smoothedG,
	}
	_, err := e.storage.LockIncident(ctx, req)
	return err
}

func magnitudeG(s Sample) float64 {
	return math.Sqrt(s.AX*s.AX + s.AY*s.AY + s.AZ*s.AZ)
}
