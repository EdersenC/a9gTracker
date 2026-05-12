package trigger

import (
	"context"
	"time"
)

// Sample is a single IMU reading in g-units.
type Sample struct {
	Timestamp time.Time
	AX        float64
	AY        float64
	AZ        float64
}

// Sensor streams IMU samples.
type Sensor interface {
	Stream(ctx context.Context) (<-chan Sample, <-chan error)
}

// LockRequest asks storage to lock pre/post incident footage.
type LockRequest struct {
	EventID    string
	TriggeredAt time.Time
	PreWindow  time.Duration
	PostWindow time.Duration
	Reason     string
	PeakG      float64
}

// LockResult is a storage lock response.
type LockResult struct {
	Locked bool
}

// StorageLocker is the storage contract used by the trigger module.
type StorageLocker interface {
	LockIncident(ctx context.Context, req LockRequest) (LockResult, error)
}
