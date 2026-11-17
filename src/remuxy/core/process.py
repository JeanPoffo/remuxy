"""Subprocess helpers: running ffmpeg/ffprobe safely and the extra input options some formats need."""
import subprocess
from pathlib import Path

from remuxy.core.constants import MPEG_PS


def run(cmd, **kw):
    """subprocess.run without inheriting stdin (otherwise ffmpeg swallows the stdin of a `while read` loop)."""
    kw.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run(cmd, **kw)


def input_options(path):
    """Extra ffmpeg/ffprobe input options for the file type (DVD VOB/MPG need deeper analysis and +genpts)."""
    if Path(path).suffix.lower() in MPEG_PS:
        return ["-analyzeduration", "200M", "-probesize", "200M", "-fflags", "+genpts"]
    return []
