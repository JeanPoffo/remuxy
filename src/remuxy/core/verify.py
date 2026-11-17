"""Output checks: sanity check of the written file and --verify, which measures the new audio against the
target's original audio inside the output (exit code 2 when the error exceeds 40 ms)."""
import statistics
import sys

from remuxy.core.consensus import consensus
from remuxy.core.constants import VERIFY_TOLERANCE
from remuxy.core.media import Media
from remuxy.core.track import get_track
from remuxy.core.windows import collect


def check_output(out, k):
    """Re-probes the output, makes sure the new track #k is there and prints video vs new audio durations."""
    chk = Media(out)
    if k >= len(chk.audios) or not chk.video:
        sys.exit("ERROR: the output does not have the expected tracks.")
    new = chk.audios[k]
    dv, da = chk.duration(chk.video), chk.duration(new)
    if dv and da:
        print(f"check: video {dv:.3f}s | new audio {da:.3f}s (difference {da - dv:+.3f}s) | "
              f"{new.get('codec_name')} {new.get('channels')}ch {new.get('channel_layout', '')}")
    return chk


def verify_sync(args, chk, k, orig_idx):
    """--verify: measures the new audio (#k) against the target's original audio in the output.
    Returns the exit code: 0 = OK/not measurable, 2 = error above the tolerance or inconclusive."""
    if not orig_idx:
        print("no original target audio in the output: nothing to compare.")
        return 0
    print("\n== Post-mux verification (new audio vs. the target's original audio) ==")
    ref = orig_idx[args.ref_audio] if args.ref_audio < len(orig_idx) else orig_idx[0]
    N, R = get_track(chk, k), get_track(chk, ref)
    pts, win = collect(N, R, 0.0, 1.0, args, 5.0, "", quiet=True)
    c = consensus(pts, 1.0, win)
    if not c:
        print("  inconclusive: the windows do not agree with each other (audio without common stretches, short "
              "movie, or a desync that varies along the movie).")
        for ts, u, z in pts:
            print(f"    t={ts:7.1f}s  error {u - ts:+.3f}s (correlation {z:.2f})")
        return 2 if len(pts) >= 3 else 0
    group = c[2]
    errs = [u - ts for ts, u, _ in group]
    worst = max(abs(e) for e in errs) * 1000
    print(f"  {len(group)} of {len(pts)} windows agree; median error {statistics.median(errs) * 1000:+.0f} ms, "
          f"max {worst:.0f} ms")
    if worst <= VERIFY_TOLERANCE * 1000:
        print("  OK (up to ~40 ms is imperceptible)")
        return 0
    if args.offset:
        print(f"  expected if --offset {args.offset:+.3f}s was an intentional deviation from the original audio; "
              "otherwise, check the result")
        return 0
    print("  ALERT: above 40 ms; check the result")
    return 2
