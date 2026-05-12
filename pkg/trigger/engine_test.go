package trigger

import (
	"context"
	"testing"
	"time"
)

type fakeSensor struct {
	samples []Sample
}

func (s *fakeSensor) Stream(ctx context.Context) (<-chan Sample, <-chan error) {
	out := make(chan Sample)
	errs := make(chan error, 1)
	go func() {
		defer close(out)
		defer close(errs)
		for _, sm := range s.samples {
			select {
			case <-ctx.Done():
				return
			case out <- sm:
			}
		}
	}()
	return out, errs
}

type lockCall struct {
	req LockRequest
}

type fakeStorage struct {
	calls []lockCall
}

func (f *fakeStorage) LockIncident(_ context.Context, req LockRequest) (LockResult, error) {
	f.calls = append(f.calls, lockCall{req: req})
	return LockResult{Locked: true}, nil
}

func TestImpactTriggersStorageLock(t *testing.T) {
	now := time.Now()
	sensor := &fakeSensor{samples: []Sample{
		{Timestamp: now, AX: 0.01, AY: 0.02, AZ: 1.0},
		{Timestamp: now.Add(20 * time.Millisecond), AX: 0.1, AY: 0.1, AZ: 3.2},
		{Timestamp: now.Add(40 * time.Millisecond), AX: 0.2, AY: 0.1, AZ: 3.3},
	}}
	storage := &fakeStorage{}
	engine := NewEngine(Config{
		ThresholdG:         2.5,
		Cooldown:           2 * time.Second,
		MinConsecutiveHits: 2,
		SmoothingAlpha:     1.0,
		MinJerkG:           0.05,
		PreWindow:          10 * time.Second,
		PostWindow:         20 * time.Second,
	}, sensor, storage)

	if err := engine.Run(context.Background()); err != nil {
		t.Fatalf("run failed: %v", err)
	}
	if len(storage.calls) != 1 {
		t.Fatalf("expected 1 lock call, got %d", len(storage.calls))
	}
	if storage.calls[0].req.Reason != "g-sensor-impact" {
		t.Fatalf("unexpected reason: %s", storage.calls[0].req.Reason)
	}
}

func TestCooldownSuppressesDuplicateEvents(t *testing.T) {
	now := time.Now()
	sensor := &fakeSensor{samples: []Sample{
		{Timestamp: now, AX: 0.0, AY: 0.0, AZ: 3.0},
		{Timestamp: now.Add(20 * time.Millisecond), AX: 0.0, AY: 0.0, AZ: 3.1},
		{Timestamp: now.Add(200 * time.Millisecond), AX: 0.0, AY: 0.0, AZ: 3.3},
		{Timestamp: now.Add(220 * time.Millisecond), AX: 0.0, AY: 0.0, AZ: 3.4},
	}}
	storage := &fakeStorage{}
	engine := NewEngine(Config{
		ThresholdG:         2.5,
		Cooldown:           3 * time.Second,
		MinConsecutiveHits: 2,
		SmoothingAlpha:     1.0,
		MinJerkG:           0.05,
	}, sensor, storage)

	if err := engine.Run(context.Background()); err != nil {
		t.Fatalf("run failed: %v", err)
	}
	if len(storage.calls) != 1 {
		t.Fatalf("expected 1 lock call due to cooldown, got %d", len(storage.calls))
	}
}

func TestFalsePositiveMitigationWithJerkGate(t *testing.T) {
	now := time.Now()
	sensor := &fakeSensor{samples: []Sample{
		{Timestamp: now, AX: 0.0, AY: 0.0, AZ: 2.6},
		{Timestamp: now.Add(20 * time.Millisecond), AX: 0.0, AY: 0.0, AZ: 2.7},
		{Timestamp: now.Add(40 * time.Millisecond), AX: 0.0, AY: 0.0, AZ: 2.65},
	}}
	storage := &fakeStorage{}
	engine := NewEngine(Config{
		ThresholdG:         2.5,
		Cooldown:           2 * time.Second,
		MinConsecutiveHits: 2,
		SmoothingAlpha:     1.0,
		MinJerkG:           0.5,
	}, sensor, storage)

	if err := engine.Run(context.Background()); err != nil {
		t.Fatalf("run failed: %v", err)
	}
	if len(storage.calls) != 0 {
		t.Fatalf("expected no lock call for low-jerk readings, got %d", len(storage.calls))
	}
}
