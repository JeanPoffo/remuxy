"""Media: one probed input file (main video, audio and subtitle streams, start times, durations and fps)."""
import sys
from fractions import Fraction
from pathlib import Path

from remuxy.core.constants import SLOW_SEEK, STD_FPS
from remuxy.core.probe import num, probe, tag_duration


class Media:
    """A probed media file. Times are normalized to the start of the file, as ffmpeg sees them."""

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_file():
            sys.exit(f"File not found: {path}")
        info = probe(path)
        self.fmt = info.get("format", {})
        self.streams = info.get("streams", [])
        kind = lambda s: s.get("codec_type")  # noqa: E731
        # main video only: embedded cover art shows up as an "attached_pic" video stream
        self.video = next((s for s in self.streams if kind(s) == "video"
                           and not (s.get("disposition") or {}).get("attached_pic")), None)
        self.audios = [s for s in self.streams if kind(s) == "audio"]
        self.subs = [s for s in self.streams if kind(s) == "subtitle"]
        self.fmt_start = num(self.fmt.get("start_time"), 0.0)
        self.fmt_dur = num(self.fmt.get("duration"))
        self.exact = {}  # stream index -> duration measured by decoding

    def slow(self):
        """True for raw formats without a time index (duration is only an estimate)."""
        return self.path.suffix.lower() in SLOW_SEEK

    def rel_start(self, s):
        """Stream start relative to the start of the file (that is how ffmpeg sees it)."""
        return num(s.get("start_time"), self.fmt_start) - self.fmt_start

    def duration(self, s):
        """Stream duration: measured value, then the stream's own, its DURATION tag, then the container's."""
        if s.get("index") in self.exact:
            return self.exact[s["index"]]
        return num(s.get("duration")) or tag_duration(s) or self.fmt_dur

    def raw_fps(self):
        """Frame rate reported by the video stream (avg_frame_rate, then r_frame_rate), or None."""
        if not self.video:
            return None
        for key in ("avg_frame_rate", "r_frame_rate"):
            try:
                f = Fraction(self.video.get(key) or "0/1")
            except (ZeroDivisionError, ValueError):
                continue
            if f > 0:
                return f
        return None

    def fps(self):
        """Nearest standard fps, or None if unknown/non-standard (VFR, mixed telecine...)."""
        f = self.raw_fps()
        if not f:
            return None
        near = min(STD_FPS, key=lambda s: abs(float(s) - float(f)))
        return near if abs(float(near) - float(f)) / float(near) < 0.005 else None
