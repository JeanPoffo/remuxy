"""Measurement windows: spreads windows over the overlap of source and target and measures each one."""
from remuxy.core.correlation import measure_point


def plan(S, T, a, b, args):
    """Windows (start in the source, duration) spread over the stretch where source and target overlap."""
    lo, hi = max(0.0, -a / b), min(S.dur, (T.dur - a) / b)
    span = hi - lo
    if span < 15:
        return [], 0.0
    win = max(min(args.window, span / 4), 5.0)
    n = args.points
    return [lo + (span - win) * (0.03 + 0.94 * i / (n - 1)) for i in range(n)], win


def collect(S, T, a0, b0, args, search, title, quiet=False):
    """Measures every planned window around the model t_target = a0 + b0 * t_source.
    Returns ([(ts, u, correlation)] of the windows above --min-score, window length)."""
    starts, win = plan(S, T, a0, b0, args)
    if not quiet:
        print(f"[auto-sync] {title}: {len(starts)} windows of {win:.0f}s, search ±{search:.0f}s")
    pts = []
    for ts in starts:
        r = measure_point(S, T, ts, a0, b0, win, search)
        if r is None:
            if not quiet:
                print(f"  t={ts:7.1f}s  (no comparable audio)")
            continue
        ts, u, z = r
        ok = z >= args.min_score
        if not quiet:
            print(f"  t={ts:7.1f}s -> target {u:9.3f}s   deviation vs predicted {u - (a0 + b0 * ts):+8.3f}s   "
                  f"correlation {z:4.2f}{'' if ok else ' (weak, discarded)'}")
        if ok:
            pts.append((ts, u, z))
    return pts, win
