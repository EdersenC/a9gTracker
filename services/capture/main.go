package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"dashcam/pkg/capture"
)

type logReporter struct{}

func (logReporter) ReportStatus(_ context.Context, s capture.Status) {
	log.Printf("status state=%s msg=%s", s.State, s.Message)
}

func (logReporter) ReportMetric(_ context.Context, m capture.Metric) {
	log.Printf("metric name=%s value=%.3f", m.Name, m.Value)
}

func (logReporter) ReportEvent(_ context.Context, e capture.Event) {
	log.Printf("event name=%s fields=%v", e.Name, e.Fields)
}

func main() {
	cfg := capture.DefaultConfig()

	flag.StringVar(&cfg.CameraDevice, "camera-device", cfg.CameraDevice, "camera device path")
	flag.StringVar(&cfg.OutputDir, "output-dir", cfg.OutputDir, "segment output directory")
	flag.IntVar(&cfg.SegmentSeconds, "segment-seconds", cfg.SegmentSeconds, "segment duration in seconds")
	flag.StringVar(&cfg.FFmpegBinary, "ffmpeg-bin", cfg.FFmpegBinary, "ffmpeg binary path")
	flag.Parse()

	pipeline, err := capture.NewPipeline(cfg, logReporter{})
	if err != nil {
		log.Fatalf("capture config invalid: %v", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := pipeline.Run(ctx); err != nil {
		log.Fatalf("capture pipeline failed: %v", err)
	}
}
