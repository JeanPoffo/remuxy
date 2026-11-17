"""Window voting: keeps only the alignment that a group of windows agrees on, ignoring isolated bad peaks."""
import math
import statistics


def consensus(pts, b0, win=0.0, tol=0.060):
    """Finds the largest group of points that agree with each other (same delay, or the same line if there is
    drift), ignoring isolated wrong measurements. Returns (a, b, group_points) or None.
    Requiring a group (instead of trusting each peak) is what allows weak correlations, like a dub's:
    false peaks land in random places and do not agree with each other.
    Neighbouring windows overlap and may repeat the same false peak, so the group must span at least
    `win` seconds (i.e. include windows that share no audio)."""
    import numpy as np
    n = len(pts)
    if n < 3:
        return None
    need = max(3, math.ceil(0.4 * n))
    hyps = [(u - b0 * ts, b0) for ts, u, _ in pts]            # constant delay
    for i in range(n):
        for j in range(i + 1, n):
            dt = pts[j][0] - pts[i][0]
            if dt >= 30:
                b = (pts[j][1] - pts[i][1]) / dt
                if abs(b / b0 - 1) <= 0.005:                   # plausible drift (up to 0.5%)
                    hyps.append((pts[i][1] - b * pts[i][0], b))
    best = []
    for a, b in hyps:
        inl = [p for p in pts if abs(p[1] - (a + b * p[0])) <= tol]
        if len(inl) > len(best) and inl[-1][0] - inl[0][0] >= win:
            best = inl
    if len(best) < need:
        return None
    res = [u - b0 * ts for ts, u, _ in best]
    if max(res) - min(res) <= tol:
        return statistics.median(res), b0, best
    b, a = (float(v) for v in np.polyfit([p[0] for p in best], [p[1] for p in best], 1))
    if max(abs(u - (a + b * ts)) for ts, u, _ in best) > 0.100 or not 0.9 <= b <= 1.1:
        return None
    return a, b, best
