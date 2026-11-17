"""Command-line options of `remux` and their validation (invalid values are rejected before any work)."""
import argparse
import re

from remuxy import __version__


def parse_args(argv=None):
    """Parses and validates the `remux` arguments; exits with a usage error on invalid values."""
    ap = argparse.ArgumentParser(prog="remux", description="Adds the audio of the SOURCE movie to the TARGET movie, in sync.",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--version", action="version", version=f"remux {__version__}")
    ap.add_argument("source", help="1st file: where the audio comes from (a movie OR an audio-only file: mp3, aac, ac3, dts, flac...)")
    ap.add_argument("target", help="2nd file: receives the audio (video/subtitles/original audio are kept)")
    ap.add_argument("-o", "--output", help="output file (default: <target>.synced.mkv)")
    ap.add_argument("--audio", type=int, default=0, help="audio track index in the SOURCE (0 = first)")
    ap.add_argument("--ref-audio", type=int, default=0, help="TARGET track used as reference by --auto-sync")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="manual fine adjustment in seconds (+ delays the new audio, - advances it)")
    ap.add_argument("--speed", type=float, help="forces the audio speed factor (e.g. 1.04271 = 23.976->25 fps)")
    ap.add_argument("--no-tempo", action="store_true", help="do not correct the speed automatically from the fps")
    ap.add_argument("--stretch", default="atempo", choices=["atempo", "resample"],
                    help="how to change the speed: atempo keeps the pitch; resample changes the pitch too "
                         "(like a real PAL speedup), is exact and has no artifacts")
    ap.add_argument("--auto-sync", action="store_true", help="measures the real delay by correlation (needs numpy)")
    ap.add_argument("--verify", action="store_true", help="measures the final result against the target's original audio")
    ap.add_argument("--points", type=int, default=12, help="number of windows measured by --auto-sync/--verify (min. 3)")
    ap.add_argument("--window", type=float, default=120, help="maximum length (s) of each compared window")
    ap.add_argument("--search", type=float, default=30,
                    help="window search ± (s) when the whole-movie correlation finds no clear peak")
    ap.add_argument("--min-score", type=float, default=0.03,
                    help="minimum correlation (0-1) for a window to take part in the vote")
    ap.add_argument("--codec", default="auto", choices=["auto", "aac", "ac3", "eac3", "libopus", "flac", "copy"],
                    help="codec of the new audio (auto = copy if AAC/AC3/E-AC3 at 48 kHz without a speed adjustment, "
                         "otherwise AAC; copy = never re-encode, except with a speed adjustment)")
    ap.add_argument("--bitrate", help="bitrate of the new audio (default: 96k per channel, max 640k)")
    ap.add_argument("--lang", help="language code of the new track (e.g. por, eng); default: the source's")
    ap.add_argument("--title", help="title of the new track")
    ap.add_argument("--default", action="store_true",
                    help="marks the new track as default (already automatic, unless --append is used)")
    ap.add_argument("--append", action="store_true",
                    help="puts the new track AFTER the originals. By default it becomes the 1st audio track, "
                         "because Plex only Direct Plays the 1st one (otherwise it remuxes and stalls on Samsung TVs)")
    ap.add_argument("--sample-rate", type=int, default=48000,
                    help="sample rate of the new audio when re-encoded (0 = keep the source's)")
    ap.add_argument("--keep-sub-default", action="store_true",
                    help="keeps the 'default' flag on image subtitles (VOBSUB/PGS). By default it is removed, "
                         "because those subtitles force a full transcode in Plex")
    ap.add_argument("--replace", action="store_true", help="removes the target's original audio tracks")
    ap.add_argument("--dry-run", action="store_true", help="only analyzes and prints the command, without writing a file")
    ap.add_argument("--overwrite", action="store_true", help="overwrites the output if it exists")
    args = ap.parse_args(argv)

    errors = []
    if args.audio < 0 or args.ref_audio < 0:
        errors.append("--audio/--ref-audio cannot be negative")
    if args.points < 3:
        errors.append("--points must be at least 3")
    if args.window <= 5 or args.search <= 0:
        errors.append("--window must be > 5 and --search > 0")
    if not 0 <= args.min_score <= 1:
        errors.append("--min-score goes from 0 to 1")
    if args.speed is not None and not 0.5 <= args.speed <= 2:
        errors.append("--speed out of the reasonable range (0.5 to 2)")
    if args.sample_rate < 0:
        errors.append("--sample-rate cannot be negative")
    if args.bitrate and not re.fullmatch(r"\d+(\.\d+)?[kKmM]?", args.bitrate):
        errors.append("invalid --bitrate (e.g. 192k, 640k)")
    if errors:
        ap.error("; ".join(errors))
    return args
