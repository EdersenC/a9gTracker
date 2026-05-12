package triggerservice

import (
	"context"
	"time"

	"dashcam/pkg/trigger"
)

// Service wires trigger engine dependencies for runtime use.
type Service struct {
	engine *trigger.Engine
}

func New(cfg trigger.Config, sensor trigger.Sensor, storage trigger.StorageLocker) *Service {
	return &Service{engine: trigger.NewEngine(cfg, sensor, storage)}
}

func (s *Service) Run(ctx context.Context) error {
	return s.engine.Run(ctx)
}

// DefaultConfig returns baseline values matching configs/trigger/default.yaml.
func DefaultConfig() trigger.Config {
	return trigger.Config{
		ThresholdG:         2.5,
		Cooldown:           8 * time.Second,
		MinConsecutiveHits: 2,
		SmoothingAlpha:     0.35,
		MinJerkG:           0.4,
		PreWindow:          15 * time.Second,
		PostWindow:         30 * time.Second,
	}
}
