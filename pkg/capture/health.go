package capture

import (
	"context"
	"sync"
	"time"
)

type ServiceState string

const (
	StateStarting ServiceState = "starting"
	StateRunning  ServiceState = "running"
	StateDegraded ServiceState = "degraded"
	StateStopped  ServiceState = "stopped"
)

const (
	MetricEncoderRestarts = "capture.encoder_restarts_total"
	MetricSegmentsFinal   = "capture.segments_finalized_total"
	MetricSegmentsOrphan  = "capture.segments_orphaned_total"
)

const (
	EventCaptureStarted    = "capture.started"
	EventCaptureStopped    = "capture.stopped"
	EventSegmentStarted    = "capture.segment.started"
	EventSegmentFinalized  = "capture.segment.finalized"
	EventSegmentOrphaned   = "capture.segment.orphaned"
	EventEncoderRestarting = "capture.encoder.restarting"
	EventCaptureError      = "capture.error"
)

type Event struct {
	Name      string
	Timestamp time.Time
	Fields    map[string]string
}

type Metric struct {
	Name      string
	Value     float64
	Timestamp time.Time
	Labels    map[string]string
}

type Status struct {
	State     ServiceState
	Timestamp time.Time
	Message   string
}

// Reporter is the health/status hook surface for runtime service integration.
type Reporter interface {
	ReportStatus(context.Context, Status)
	ReportMetric(context.Context, Metric)
	ReportEvent(context.Context, Event)
}

type NopReporter struct{}

func (NopReporter) ReportStatus(context.Context, Status) {}
func (NopReporter) ReportMetric(context.Context, Metric) {}
func (NopReporter) ReportEvent(context.Context, Event)   {}

type HealthSnapshot struct {
	State                ServiceState
	LastError            string
	LastHeartbeat        time.Time
	LastSegmentStarted   time.Time
	LastSegmentFinalized time.Time
	SegmentsFinalized    uint64
	SegmentsOrphaned     uint64
	EncoderRestarts      uint64
}

type healthStore struct {
	mu sync.RWMutex
	s  HealthSnapshot
}

func (h *healthStore) snapshot() HealthSnapshot {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.s
}

func (h *healthStore) update(fn func(*HealthSnapshot)) {
	h.mu.Lock()
	defer h.mu.Unlock()
	fn(&h.s)
	h.s.LastHeartbeat = time.Now().UTC()
}
