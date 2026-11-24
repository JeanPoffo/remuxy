"""--auto-sync: measures the real alignment between the source audio and the target's original audio.

Whole-movie correlation per candidate speed, then voting windows; reports drift and different cuts.
"""
from remuxy.core.coarse import coarse
from remuxy.core.consensus import consensus
from remuxy.core.correlation import measure_point
from remuxy.core.windows import collect


def auto_sync(S, T, a0, b0, alts, args):
    """Measures the real alignment. Returns (a, b) or None.
      1) whole-movie correlation for each candidate speed -> rough delay, with no search limit
      2) windows spread over the movie around that delay -> fine delay, drift and different cuts
    """
    a1, b1, search, zg = a0, b0, args.search, 0.0
    cs = coarse(S, T, [b0] + [x for x in alts if abs(x - b0) > 1e-9])
    if cs:
        print("[auto-sync] whole-movie correlation per candidate speed:")
        for b, a, z in cs:
            print(f"  {1 / b:.5f}x  delay {a:+9.3f}s  prominence {z:5.1f}{'  (predicted)' if abs(b - b0) < 1e-9 else ''}")
        pred = next((c for c in cs if abs(c[0] - b0) < 1e-9), None)
        top = max(cs, key=lambda c: c[2])
        if pred and pred[2] >= 8 and top[2] < 1.25 * pred[2]:
            top = pred  # the predicted speed only loses if another one is clearly better
        if top[2] >= 8:
            b1, a1, zg = top
            search = min(args.search, 5.0)
            if abs(b1 - b0) > 1e-9:
                print(f"  -> speed {1 / b1:.5f}x explains the audio better than the predicted one ({1 / b0:.5f}x); using it")
        else:
            print("  -> no clear peak over the whole movie (drift, different cuts or unrelated audio); "
                  "trying windows around the prediction")
    pts, win = collect(S, T, a1, b1, args, search, "windows")
    c = consensus(pts, b1, win)
    if c and abs(c[1] - b1) > 1e-9:
        print(f"  drift detected: speed {1 / c[1]:.6f}x; refining with the drift compensated")
        pts2, win2 = collect(S, T, c[0], c[1], args, 2.0, "windows (2nd pass)")
        c2 = consensus(pts2, c[1], win2)
        if c2:
            c, pts, win = c2, pts2, win2
    if c:
        a, b, group = c
        left_out = len(pts) - len(group)
        print(f"  {len(group)} of {len(pts)} windows agree: delay {a:+.3f}s, speed {1 / b:.6f}x")
        if left_out:
            # the windows left out: noise, or a stretch with ANOTHER delay (different cuts)?
            # measure only those again, with a very wide search, and see whether they agree with each other
            wide = max(args.search, 120.0)
            rest = [r for r in (measure_point(S, T, p[0], a, b, win, wide) for p in pts if p not in group) if r]
            c2 = consensus(rest, b, 0.0) if len(rest) >= 3 else None
            if c2 and abs(c2[0] - a) > 0.1:
                t0, t1 = c2[2][0][0], c2[2][-1][0] + win
                print(f"  WARNING: {len(c2[2])} windows (between {t0:.0f}s and {t1:.0f}s of the source) agree on ANOTHER "
                      f"delay ({c2[0]:+.3f}s). The movies have different cuts: that stretch will be "
                      f"{abs(c2[0] - a):.2f}s out of sync. A single adjustment cannot fix both stretches"
                      f"{'' if args.segments else '; use --segments to splice the new audio per stretch'}.")
            else:
                print(f"  ({left_out} windows without a reliable peak were ignored; normal when the dialogue differs)")
        return a, b
    if zg >= 12:
        print(f"  windows inconclusive; using only the whole-movie correlation (delay {a1:+.3f}s, lower precision)")
        return a1, b1
    print("  inconclusive measurement: no group of windows agreeing. The movies may have different cuts "
          "or the audio tracks share no common stretches.")
    return None
