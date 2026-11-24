#!/usr/bin/env python3
"""
remux - copies an audio track from one movie (SOURCE) into another (TARGET),
keeping it in sync with the target's video.

    remux SOURCE TARGET [options]          (installed)
    python3 -m remuxy.remux SOURCE TARGET  (without installing)

What it checks/fixes:
  1. Start of each stream (start_time) -> compensates the audio offset inside the container.
  2. Video fps/duration                -> detects the classic 23.976 <-> 24 <-> 25 fps case
                                          and adjusts the audio speed (atempo, pitch preserved).
  3. (--auto-sync) measures the real alignment by comparing the SOURCE audio with the TARGET's original
     audio: first a whole-movie correlation for each candidate speed (finds the delay with no search
     limit and confirms/corrects the speed), then windows spread over the movie that vote: only what
     the majority agrees on counts. So it works with dubs (different dialogue; music/effects match),
     detects drift and warns about different cuts. When the source also carries the target reference's
     language (a dubbed release that keeps the original track), that track is measured instead: same file,
     same timeline, much stronger match (--sync-audio forces the choice).
     (--segments) for releases with different cuts: maps the delay along the whole movie with the new track,
     and splices it per stretch (silence inserted / audio dropped at the quietest point of each change).
  4. (--verify) after writing the file, measures the new audio against the target's original audio.
     Exits with code 2 if the error exceeds 40 ms.

The SOURCE can be a movie OR an audio-only file (mp3, aac, m4a, ac3, eac3, dts, flac, wav, mka...).
Without video in the source, the speed is deduced by comparing the audio duration with the target's video.
For "raw" audio (mp3, aac, ac3, dts...) the duration reported by ffprobe may only be a bitrate estimate;
for those formats the track is decoded once to measure the exact duration.

Speed detection (NTSC/PAL DVD): the reported fps lies (an NTSC film DVD usually reports 29.97 because of
pulldown, but the film runs at 23.976). The possible real speeds of each side are considered and the
combination that matches the duration ratio wins (e.g. 23.976 -> 25 fps = PAL speedup).

Plex/TV compatibility (Direct Play):
  - the new track becomes the 1st audio track and the default (--append puts it last);
  - new audio at 48 kHz; image subtitles (VOBSUB/PGS) lose the "default" flag;
  - audio correctly interleaved with the video (checked at the end);
  - writes to ".<output>.part" and only renames it when done.

Requirements: ffmpeg + ffprobe on PATH. --auto-sync/--verify need numpy.

This module orchestrates the steps; each step lives in its own module under `remuxy.core`.
"""
import importlib.util
import math
import shlex
import shutil
import signal
import sys
from pathlib import Path

from remuxy.core.arguments import parse_args
from remuxy.core.audio_filter import build_filter
from remuxy.core.auto_sync import auto_sync
from remuxy.core.codec import resolve_codec
from remuxy.core.interleave import check_interleave
from remuxy.core.media import Media
from remuxy.core.mux_command import build_mux_command
from remuxy.core.prior_model import prior_model
from remuxy.core.segments import segment_map, splice_steps
from remuxy.core.process import run
from remuxy.core.sync_track import pick_ref_track, pick_sync_track
from remuxy.core.track import get_track
from remuxy.core.verify import check_output, verify_sync


def main(argv=None):
    """Runs one remux: analysis, timing model, optional measurement, mux and checks. Returns the exit code."""
    args = parse_args(argv)
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH.")
    if (args.auto_sync or args.verify) and importlib.util.find_spec("numpy") is None:
        sys.exit("--auto-sync/--verify need numpy (pip install numpy).")

    src, tgt = Media(args.source), Media(args.target)
    if not tgt.video:
        sys.exit("The target needs a video stream (it is the time reference).")
    if args.audio >= len(src.audios):
        sys.exit(f"The source has {len(src.audios)} audio track(s); --audio {args.audio} does not exist.")
    if not tgt.duration(tgt.video):
        sys.exit("Could not read the duration of the target's video.")
    ref_note = None
    if args.auto_sync or args.verify:
        args.ref_audio, ref_note = pick_ref_track(src, tgt, args)
    elif args.ref_audio is None:
        args.ref_audio = 0
    if args.auto_sync and args.ref_audio >= len(tgt.audios):
        sys.exit(f"The target has {len(tgt.audios)} audio track(s); there is no --ref-audio "
                 f"{args.ref_audio} reference for --auto-sync.")
    if args.sync_audio is not None and args.sync_audio >= len(src.audios):
        sys.exit(f"The source has {len(src.audios)} audio track(s); --sync-audio {args.sync_audio} does not exist.")
    sa = src.audios[args.audio]
    a_s = src.rel_start(sa)
    ch = int(sa.get("channels") or 2)

    if not src.video and src.slow():
        if importlib.util.find_spec("numpy") is None:
            print(f"WARNING: without numpy the exact duration of {src.path.name} cannot be measured; "
                  "the reported duration may be only an estimate.")
        else:
            est = src.duration(sa)
            print(f"measuring the exact duration of {src.path.name} (format without a time index)...")
            real = get_track(src, args.audio).dur
            src.exact[sa["index"]] = real
            if est and abs(real - est) > 0.5:
                print(f"  ffprobe estimated {est:.3f}s; real duration {real:.3f}s (corrected)")

    print("== Analysis ==")
    for name, m in (("SOURCE", src), ("TARGET", tgt)):
        if not m.video:
            print(f"{name}: audio only ({m.path.suffix.lstrip('.') or '?'}) | {len(m.audios)} audio track(s)")
            continue
        raw = m.raw_fps()
        print(f"{name}: video {m.duration(m.video) or 0:.3f}s @ {f'{float(raw):.3f}' if raw else '?'}fps "
              f"(start {m.rel_start(m.video):+.3f}s) | {len(m.audios)} audio track(s)")
    dur_sa = src.duration(sa)
    print(f"source audio chosen: #{args.audio} {sa.get('codec_name')} {ch}ch "
          f"{sa.get('channel_layout') or ''} start {a_s:+.3f}s dur {f'{dur_sa:.3f}s' if dur_sa else '?'}")

    a, b, notes, alts = prior_model(src, tgt, args)
    b_prior = b
    for n in notes:
        print(" -", n)

    bounds = []
    if args.auto_sync:
        if ref_note:
            print(f"[auto-sync] {ref_note}")
        sync_idx, note = pick_sync_track(src, tgt, args)
        if note:
            print(f"[auto-sync] {note}")
        S, T = get_track(src, sync_idx), get_track(tgt, args.ref_audio)
        for name, tr in (("source", S), ("target", T)):
            if tr.no_center:
                print(f"  {name}: comparing only the side channels (the center, with the dialogue, is left out)")
        r = auto_sync(S, T, a, b, alts, args)
        if r and args.segments:
            # mapped with the new track itself: it is what has to line up, and a dub may have its own small edits
            N = get_track(src, args.audio) if sync_idx != args.audio else S
            m = segment_map(src, args.audio, N, T, r[0], r[1], b_prior, args)
            if m is None and N is not S:
                print(f"  trying again with source track #{sync_idx}")
                m = segment_map(src, args.audio, S, T, r[0], r[1], b_prior, args)
            if m:
                r, bounds = (m[0], m[2]), m[1]
        if r:
            # the measurement is absolute; the manual fine adjustment goes on top of it
            a, b = r[0] + args.offset, r[1]
            if args.offset:
                print(f"  + manual offset {args.offset:+.3f}s applied on top of the measurement")
        else:
            print("  -> keeping the model computed from the metadata.")

    out_end = tgt.rel_start(tgt.video) + tgt.duration(tgt.video)
    steps = splice_steps(a - args.offset, bounds, a_s, b) if bounds else None  # the offset shifts every stretch
    codec, sr, src_sr, ch_out = resolve_codec(args, sa, b, ch, delay=a + b * a_s, spliced=bool(steps))
    copy = codec == "copy"
    flt, delay = build_filter(a, b, a_s, ch, out_end, codec, sample_rate=sr or None, src_sr=src_sr,
                              stretch=args.stretch, steps=steps)
    if abs(b - 1) > 1e-9 and not copy:
        semis = 12 * math.log2(1 / b)
        if args.stretch == "resample" and src_sr:
            print(f" - speed adjustment by resampling: the pitch changes {semis:+.2f} semitone (like a real PAL speedup)")
        else:
            print(" - speed adjustment with atempo: the pitch is kept (--stretch resample = exact, but changes the pitch "
                  f"{semis:+.2f} semitone)")
    print(f"\n== Result of the calculation ==\n  initial delay of the new audio: {delay:+.3f}s | "
          f"speed: {1 / b:.6f}x | ends at {out_end:.3f}s"
          + (f" | {len(steps)} splice(s) (--segments)" if steps else ""))
    if copy:
        # copy without re-encoding: the shift is applied to the packet timestamps (exact);
        # whatever falls before the start is dropped in whole packets (up to ~32 ms less audio at the start)
        if delay < -0.0005:
            print(f"  --codec copy: the first {-delay:.3f}s of the audio are dropped (no re-encoding)")
        if dur_sa and delay + dur_sa > out_end + 1.0:
            print(f"  --codec copy: the new audio runs {delay + dur_sa - out_end:.1f}s past the end of the video "
                  "(kept as is; re-encoding would cut it)")

    out = Path(args.output) if args.output else tgt.path.with_name(tgt.path.stem + ".synced.mkv")
    if out.exists() and not args.overwrite and not args.dry_run:
        sys.exit(f"{out} already exists (use --overwrite or -o).")
    if out.resolve() in (src.path.resolve(), tgt.path.resolve()):
        sys.exit("The output cannot be one of the input files.")
    if out.suffix.lower() not in (".mkv", ".mka", ".mk3d"):
        print(f"WARNING: the output is always Matroska; use the .mkv extension instead of '{out.suffix}'.")
    if not out.parent.is_dir():
        sys.exit(f"The output folder does not exist: {out.parent}")

    # Writes to a hidden file (Plex ignores files starting with ".") and only renames it at the end:
    # Plex never scans a half-written file, and a failure leaves nothing with the final name.
    tmp = out.with_name(f".{out.name}.part")
    cmd, k, orig_idx = build_mux_command(args, src, tgt, sa, codec, flt, a, ch_out, tmp)

    print("\n$", shlex.join(cmd))
    if args.dry_run:
        return 0
    tmp.unlink(missing_ok=True)
    try:
        rc = run(cmd).returncode
    except KeyboardInterrupt:
        tmp.unlink(missing_ok=True)
        sys.exit("\nInterrupted; partial file removed.")
    if rc:
        tmp.unlink(missing_ok=True)
        sys.exit("ffmpeg failed.")
    tmp.replace(out)
    print(f"\nOK: {out}")
    check_interleave(out, k)
    chk = check_output(out, k)
    if not args.verify:
        return 0
    return verify_sync(args, chk, k, orig_idx)


def _sigterm(*_):
    raise KeyboardInterrupt


def cli() -> None:
    """Entry point of the `remux` command."""
    signal.signal(signal.SIGTERM, _sigterm)  # kill/timeout also clean up the partial file
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")


if __name__ == "__main__":
    cli()
