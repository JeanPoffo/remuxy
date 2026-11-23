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


def first_pts(path, index, packets=20):
    """Earliest timestamp (s) among the first packets of stream `index`, or None if none could be read.

    A stream's `start_time` is not always where its audio really begins: a Matroska track whose first packet
    sits at 16.7 s can still report start_time 0. Reading the packets themselves gives the real start.
    """
    r = run(["ffprobe", "-v", "error"] + input_options(path)
            + ["-select_streams", str(index), "-read_intervals", f"%+#{packets}",
               "-show_entries", "packet=pts_time,dts_time", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True)
    if r.returncode:
        return None
    ts = [num(v) for line in r.stdout.splitlines() for v in line.split(",")[:1]]
    ts = [t for t in ts if t is not None]
    return min(ts) if ts else None


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
