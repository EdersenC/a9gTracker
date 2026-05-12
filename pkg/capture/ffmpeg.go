package capture

import (
	"fmt"
)

func buildFFmpegArgs(cfg Config, segmentStartNumber int64) []string {
	gop := cfg.FPS * 2
	return []string{
		"-nostdin",
		"-hide_banner",
		"-loglevel", "warning",
		"-f", "v4l2",
		"-thread_queue_size", "512",
		"-framerate", fmt.Sprintf("%d", cfg.FPS),
		"-video_size", fmt.Sprintf("%dx%d", cfg.Width, cfg.Height),
		"-i", cfg.CameraDevice,
		"-an",
		"-c:v", cfg.VideoCodec,
		"-r", fmt.Sprintf("%d", cfg.FPS),
		"-g", fmt.Sprintf("%d", gop),
		"-keyint_min", fmt.Sprintf("%d", gop),
		"-sc_threshold", "0",
		"-pix_fmt", "yuv420p",
		"-f", "segment",
		"-segment_time", fmt.Sprintf("%d", cfg.SegmentSeconds),
		"-reset_timestamps", "1",
		"-segment_format", "mp4",
		"-segment_start_number", fmt.Sprintf("%d", segmentStartNumber),
		"-segment_list", cfg.SegmentListPath(),
		"-segment_list_type", "csv",
		cfg.SegmentTempPattern(),
	}
}
