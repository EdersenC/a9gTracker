package sensors

import (
	"context"
	"time"

	"dashcam/pkg/trigger"
)

// SimulatedSensor replays deterministic samples for tests and local simulation.
type SimulatedSensor struct {
	Samples  []trigger.Sample
	Interval time.Duration
}

func (s *SimulatedSensor) Stream(ctx context.Context) (<-chan trigger.Sample, <-chan error) {
	out := make(chan trigger.Sample)
	errCh := make(chan error, 1)

	go func() {
		defer close(out)
		defer close(errCh)
		interval := s.Interval
		if interval <= 0 {
			interval = 20 * time.Millisecond
		}
		base := time.Now()
		for i, sample := range s.Samples {
			if sample.Timestamp.IsZero() {
				sample.Timestamp = base.Add(time.Duration(i) * interval)
			}
			select {
			case <-ctx.Done():
				return
			case out <- sample:
			}
			if i != len(s.Samples)-1 {
				select {
				case <-ctx.Done():
					return
				case <-time.After(interval):
				}
			}
		}
	}()

	return out, errCh
}
