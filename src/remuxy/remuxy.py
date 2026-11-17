#!/usr/bin/env python3
"""
remuxy - terminal UI (TUI) for remux.

    remuxy [SOURCE] [TARGET]

Choose the source (where the audio comes from), the target (the movie that receives the audio) and the
output, set the options and press Start. Progress shows in the bar and the remux/ffmpeg output in the log.

Requirements: textual (pip install textual), ffmpeg/ffprobe and, for --auto-sync/--verify, numpy.
"""
import sys

from remuxy import __version__


def main() -> None:
    """Entry point of the `remuxy` command."""
    a = sys.argv[1:]
    if a and a[0] in ("-h", "--help"):
        print(__doc__)
        return
    if a and a[0] == "--version":
        print(f"remuxy {__version__}")
        return
    from remuxy.tui.app import RemuxY  # imported here so --help/--version work without Textual
    RemuxY(*(a + ["", ""])[:2]).run()


if __name__ == "__main__":
    main()
