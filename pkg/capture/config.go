package capture

import (
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"time"
)

const (
	defaultCameraID       = "front"
	defaultCameraDevice   = "/dev/video0"
	defaultOutputDir      = "/var/lib/dashcam/capture"
	defaultSegmentSeconds = 60
)

// Config defines capture pipeline configuration for a single front camera.
type Config struct {
	CameraID       string
	CameraDevice   string
	OutputDir      string
	Width          int
	Height         int
	FPS            int
	SegmentSeconds int
	VideoCodec     string
	FFmpegBinary   string
	RestartBackoff time.Duration
}

func DefaultConfig() Config {
	return Config{
		CameraID:       defaultCameraID,
		CameraDevice:   defaultCameraDevice,
		OutputDir:      defaultOutputDir,
		Width:          1280,
		Height:         720,
		FPS:            30,
		SegmentSeconds: defaultSegmentSeconds,
		VideoCodec:     "h264_v4l2m2m",
		FFmpegBinary:   "ffmpeg",
		RestartBackoff: 2 * time.Second,
	}
}

func (c Config) Validate() error {
	if strings.TrimSpace(c.CameraID) == "" {
		return errors.New("camera_id is required")
	}
	if strings.TrimSpace(c.CameraDevice) == "" {
		return errors.New("camera_device is required")
	}
	if strings.TrimSpace(c.OutputDir) == "" {
		return errors.New("output_dir is required")
	}
	if c.Width != 1280 || c.Height != 720 {
		return fmt.Errorf("only 1280x720 is supported in v1, got %dx%d", c.Width, c.Height)
	}
	if c.FPS != 30 {
		return fmt.Errorf("only 30fps is supported in v1, got %d", c.FPS)
	}
	if c.SegmentSeconds <= 0 {
		return errors.New("segment_seconds must be > 0")
	}
	if strings.TrimSpace(c.VideoCodec) == "" {
		return errors.New("video_codec is required")
	}
	if strings.TrimSpace(c.FFmpegBinary) == "" {
		return errors.New("ffmpeg_binary is required")
	}
	if c.RestartBackoff < 0 {
		return errors.New("restart_backoff cannot be negative")
	}
	return nil
}

func (c Config) SegmentListPath() string {
	return filepath.Join(c.OutputDir, fmt.Sprintf("%s_segments.csv", c.CameraID))
}

func (c Config) SegmentTempPattern() string {
	return filepath.Join(c.OutputDir, fmt.Sprintf("%s_%%010d.mp4.partial", c.CameraID))
}

func (c Config) SegmentStartNumber(now time.Time) int64 {
	if c.SegmentSeconds <= 0 {
		return 0
	}
	return now.UTC().Unix() / int64(c.SegmentSeconds)
}
