"""--segments: maps the delay along the whole movie and splices the new audio per stretch.

Two releases of a movie can differ by small edits (a few frames cut here, a shot extended there, a logo at the
start). A single delay then only fits part of the movie. This module measures short windows over the whole
movie, groups consecutive windows that agree into stretches, finds where each change happens and picks the
quietest instant of the new audio around it to cut. The splice itself is applied by the audio filter: when the
delay grows, silence is inserted; when it shrinks, that much of the new audio is dropped.
"""
import statistics

from remuxy.core.correlation import measure_point
from remuxy.core.process import input_options, run

SCAN_WIN, SCAN_STEP = 20.0, 10.0  # dense scan: 20 s windows every 10 s
FINE_WIN = 6.0                    # windows used to locate each change (5 s is the correlation minimum)
TOL = 0.045                       # a window agrees with a stretch within this (s)
RUN = 3                           # consecutive agreeing windows needed to open a new stretch
SMALL = 0.15                      # changes smaller than this (s) need twice as many windows (they look like noise)
MERGE = 0.080                     # neighbouring stretches closer than this are one (s): ~2 frames, below that the
                                  # dub-vs-original measurement itself wanders
MIN_Z = 0.10                      # minimum correlation of a scan window
QUIET_R = 3.0                     # the cut goes at the quietest point within ± this of the located change (s)


def clock(t):
    """Seconds as H:MM:SS.s."""
    t = max(t, 0.0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:04.1f}"


def scan(S, T, a, b, search):
    """Dense scan around t_target = a + b * t_source. Returns [(ts, delay, correlation)] of the reliable windows,
    where delay = u - b * ts (the local value of a), and the number of windows measured."""
    lo, hi = max(0.0, -a / b), min(S.dur, (T.dur - a) / b) - SCAN_WIN
    pts, n, ts = [], 0, lo
    while ts <= hi:
        r = measure_point(S, T, ts, a, b, SCAN_WIN, search)
        n += 1
        if r and r[2] >= MIN_Z:
            pts.append((r[0], r[1] - b * r[0], r[2]))
        ts += SCAN_STEP
    return pts, n


def _run(pts, i, need):
    """Median delay of pts[i:i+need] when those windows all agree with each other, else None."""
    run_ = pts[i:i + need]
    if len(run_) < need:
        return None
    m = statistics.median(p[1] for p in run_)
    return m if all(abs(p[1] - m) <= TOL for p in run_) else None


def split(pts):
    """Groups consecutive windows into stretches of the same delay. A new stretch needs RUN consecutive windows
    agreeing with each other (2 * RUN for a change under SMALL, which looks more like noise); isolated windows that
    agree with nothing are ignored. Returns [[(ts, delay, z), ...], ...] in source order."""
    segs, cur, i = [], None, 0
    while i < len(pts):
        if cur and abs(pts[i][1] - delay(cur)) <= TOL:
            cur.append(pts[i])
            i += 1
            continue
        m = _run(pts, i, RUN)
        need = RUN if m is not None and (cur is None or abs(m - delay(cur)) >= SMALL) else 2 * RUN
        if need > RUN:
            m = _run(pts, i, need)
        if m is None:
            i += 1  # outlier
            continue
        if cur:
            segs.append(cur)
        cur, i = list(pts[i:i + need]), i + need
    if cur:
        segs.append(cur)
    merged = []  # neighbours whose delays barely differ are one stretch (measurement noise)
    for seg in segs:
        if merged and abs(delay(merged[-1]) - delay(seg)) <= MERGE:
            merged[-1] = merged[-1] + seg
        else:
            merged.append(seg)
    return merged


def pooled_slope(segs):
    """Common slope of the delay inside the stretches (s per s): a leftover drift the stretches share."""
    num = den = 0.0
    for seg in segs:
        if len(seg) < 3:
            continue
        mt = sum(p[0] for p in seg) / len(seg)
        mo = sum(p[1] for p in seg) / len(seg)
        num += sum((p[0] - mt) * (p[1] - mo) for p in seg)
        den += sum((p[0] - mt) ** 2 for p in seg)
    return num / den if den else 0.0


def delay(seg):
    """Median delay of a stretch."""
    return statistics.median(p[1] for p in seg)


def locate(S, T, b, t0, t1, oa, ob):
    """Where, between source times t0 and t1, the delay changes from `oa` to `ob`, measured with short windows.
    Returns the source time of the change."""
    half = abs(ob - oa) / 2
    mid = (oa + ob) / 2
    labels, t = [], t0
    while t + FINE_WIN <= t1:
        r = measure_point(S, T, t, mid, b, FINE_WIN, half + 0.5)
        if r and r[2] >= MIN_Z:
            d = r[1] - b * r[0]
            da, db = abs(d - oa), abs(d - ob)
            if min(da, db) <= half + 0.02:
                labels.append((r[0] + FINE_WIN / 2, da <= db))
        t += 1.0
    if not labels:
        return (t0 + t1) / 2
    # the change point that best separates "before" (agrees with oa) from "after" (agrees with ob)
    cands = [labels[0][0] - 0.5] + [c + 0.5 for c, _ in labels]
    score = lambda c: sum(1 for x, is_a in labels if (x < c) == is_a)  # noqa: E731
    best = max(score(c) for c in cands)
    hits = [c for c in cands if score(c) == best]
    return (hits[0] + hits[-1]) / 2


def quiet_point(media, aidx, lo, hi):
    """Quietest instant (0.3 s average) of audio #aidx of `media` between lo and hi (source times).
    Returns (time, level in dBFS), or (center, None) if it could not be decoded."""
    import numpy as np
    lo = max(lo, 0.0)
    pos = ["-i", str(media.path), "-ss", f"{lo:.3f}"] if media.slow() else ["-ss", f"{lo:.3f}", "-i", str(media.path)]
    r = run(["ffmpeg", "-v", "error", "-nostdin"] + input_options(media.path) + pos
            + ["-t", f"{hi - lo:.3f}", "-map", f"0:a:{aidx}", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
            capture_output=True)
    x = np.frombuffer(r.stdout[: len(r.stdout) // 4 * 4], dtype=np.float32) if not r.returncode else np.zeros(0)
    blk, k = 200, 12  # 25 ms blocks, 0.3 s average
    if len(x) < blk * k:
        return (lo + hi) / 2, None
    p = (x[: len(x) // blk * blk].astype(np.float64).reshape(-1, blk) ** 2).mean(axis=1)
    m = np.convolve(p, np.ones(k) / k, mode="valid")
    i = int(np.argmin(m))
    return lo + (i + k / 2) * blk / 8000, float(10 * np.log10(max(m[i], 1e-12)))


def segment_map(src, aidx, S, T, a, b, b_prior, args):
    """Maps the delay of the new audio along the whole movie.
    S = decoded source track measured, T = target reference, (a, b) = alignment found by --auto-sync,
    b_prior = speed from the metadata.
    Returns (initial delay, [(source time of the cut, delay from there on), ...], speed) or None if inconclusive."""
    search = max(args.search, 5.0)
    print(f"[segments] mapping the delay along the movie: {SCAN_WIN:.0f}s windows every {SCAN_STEP:.0f}s, "
          f"search ±{search:.0f}s", flush=True)
    pts, n = scan(S, T, a, b, search)
    if len(pts) < max(RUN, 0.25 * n):
        print(f"  only {len(pts)} of {n} windows have a reliable peak: cannot map the movie; "
              "keeping the single delay")
        return None
    segs = split(pts)
    # Different cuts fool the drift estimate of --auto-sync (a jump looks like a slope). The speed is refitted from
    # the slope left inside the stretches, and the metadata speed wins when they differ by a negligible drift.
    b2 = b + pooled_slope(segs)
    if abs(b2 - b_prior) * S.dur < 0.1:
        b2 = b_prior
    if abs(b2 - b) > 1e-9:
        print(f"  speed refitted from the stretches: {1 / b:.6f}x -> {1 / b2:.6f}x")
        pts = [(ts, d + (b - b2) * ts, z) for ts, d, z in pts]
        b, segs = b2, split(pts)
    print(f"  {len(pts)} of {n} windows reliable; {len(segs)} stretch(es)")
    if not segs:
        return None
    for s in segs:
        print(f"  stretch {clock(s[0][0])} - {clock(s[-1][0] + SCAN_WIN)} (source): delay {delay(s):+.3f}s "
              f"({len(s)} windows)")
    if len(segs) > 40:
        print("  WARNING: too many stretches; the measurement looks noisy. Check the result with --verify.")
    o0, bounds, last = delay(segs[0]), [], -1e9
    for prev, nxt in zip(segs, segs[1:]):
        oa, ob = delay(prev), delay(nxt)
        t0, t1 = prev[-1][0], nxt[0][0] + SCAN_WIN
        c = locate(S, T, b, t0, t1, oa, ob)
        p, db = quiet_point(src, aidx, c - QUIET_R, c + QUIET_R)
        p = max(p, last + 0.1)  # never before the end of the previous change
        step = (ob - oa) / b
        what = (f"inserts {step:.3f}s of silence" if step > 0 else f"drops {-step:.3f}s of the new audio")
        level = f"{db:.0f} dB" if db is not None else "level unknown"
        print(f"  cut at {clock(p)} (source; change located at {clock(c)}, quietest point {level}): "
              f"{oa:+.3f}s -> {ob:+.3f}s, {what}")
        bounds.append((p, ob))
        last = p + max(-step, 0.0)
    return o0, bounds, b


def splice_steps(o0, bounds, a_s, b):
    """Converts the cuts to the audio filter's terms: [(position in the source stream, seconds to insert (+) or
    drop (-))]. The stream time starts at the first audio sample (a_s) and runs before any speed change."""
    steps, prev = [], o0
    for p, o in bounds:
        steps.append((max(p - a_s, 0.0), (o - prev) / b))
        prev = o
    return steps
