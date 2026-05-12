package trigger

import "time"

// Config controls impact detection behavior.
type Config struct {
	ThresholdG         float64
	Cooldown           time.Duration
	MinConsecutiveHits int
	SmoothingAlpha     float64
	MinJerkG           float64
	PreWindow          time.Duration
	PostWindow         time.Duration
}

func (c Config) withDefaults() Config {
	if c.ThresholdG <= 0 {
		c.ThresholdG = 2.5
	}
	if c.Cooldown <= 0 {
		c.Cooldown = 8 * time.Second
	}
	if c.MinConsecutiveHits <= 0 {
		c.MinConsecutiveHits = 2
	}
	if c.SmoothingAlpha <= 0 || c.SmoothingAlpha > 1 {
		c.SmoothingAlpha = 0.35
	}
	if c.MinJerkG <= 0 {
		c.MinJerkG = 0.4
	}
	if c.PreWindow <= 0 {
		c.PreWindow = 15 * time.Second
	}
	if c.PostWindow <= 0 {
		c.PostWindow = 30 * time.Second
	}
	return c
}
