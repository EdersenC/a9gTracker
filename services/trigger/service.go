package triggerservice

import (
	"context"

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

// DefaultConfig returns baseline trigger defaults.
func DefaultConfig() trigger.Config {
	return trigger.Config{}
}
