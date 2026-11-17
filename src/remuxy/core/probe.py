"""ffprobe wrapper plus small parsers for the values it returns (numbers and Matroska DURATION tags)."""
import json
import re
import sys

from remuxy.core.process import input_options, run


def probe(path):
    """Returns ffprobe's JSON (format + streams) for `path`; exits with a message if it cannot be read."""
    r = run(["ffprobe", "-v", "error"] + input_options(path) + ["-print_format", "json",
             "-show_format", "-show_streams", str(path)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffprobe failed on {path}:\n{r.stderr.strip()}")
    try:
        return json.loads(r.stdout or "{}")
    except ValueError:
        sys.exit(f"ffprobe returned unreadable output for {path}")


def num(x, default=None):
    """float(x), or `default` when x is missing or not a number."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def tag_duration(stream):
    """Duration in seconds from a Matroska `DURATION` tag (HH:MM:SS.fff), or None."""
    for k, v in (stream.get("tags") or {}).items():
        if k.upper().startswith("DURATION"):
            m = re.match(r"(\d+):(\d+):([\d.]+)", str(v))
            if m:
                return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    return None
