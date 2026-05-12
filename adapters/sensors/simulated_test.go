package sensors

import (
	"context"
	"testing"
	"time"

	"dashcam/pkg/trigger"
)

func TestSimulatedSensorStreamsAllSamples(t *testing.T) {
	sim := &SimulatedSensor{
		Samples: []trigger.Sample{
			{AX: 0, AY: 0, AZ: 1},
			{AX: 0, AY: 1, AZ: 1},
			{AX: 1, AY: 1, AZ: 1},
		},
		Interval: 1 * time.Millisecond,
	}

	ch, errs := sim.Stream(context.Background())
	count := 0
	for range ch {
		count++
	}
	if err := <-errs; err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if count != 3 {
		t.Fatalf("expected 3 samples, got %d", count)
	}
}
