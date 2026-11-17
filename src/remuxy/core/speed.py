"""Speed detection: real playback speeds behind a reported fps (NTSC pulldown, interlacing) and choosing the
source/target speed ratio that matches the files' durations."""
from fractions import Fraction

from remuxy.core.constants import FILM


def true_rates(fps):
    """Possible real content speeds for the reported fps, by priority. [] = unknown.
    NTSC film DVDs report 29.97 (pulldown) although the film runs at 23.976;
    interlaced video may report the field rate (50 / 59.94)."""
    if not fps:
        return []
    f = float(fps)
    if abs(f - 30000 / 1001) < 0.05:
        return [Fraction(24000, 1001), fps]
    if abs(f - 30) < 0.05:
        return [Fraction(24), fps]
    if abs(f - 60000 / 1001) < 0.05:
        return [Fraction(24000, 1001), Fraction(30000, 1001), fps]
    if abs(f - 60) < 0.05:
        return [Fraction(24), Fraction(30), fps]
    if abs(f - 50) < 0.05:
        return [Fraction(25), fps]
    return [fps]


def speed_candidates(S, T):
    """Possible ratios b = target_time / source_time, as (b, source_fps, target_fps).
    A side with unknown fps (audio-only source, VFR...) is assumed to be film at 23.976, 24 or 25."""
    out = []
    for rs in (S or FILM):
        for rt in (T or FILM):
            b = float(rs / rt)
            if 0.9 <= b <= 1.1 and all(abs(b - o[0]) > 1e-9 for o in out):
                out.append((b, rs, rt))
    uncertain = len(S) != 1 or len(T) != 1  # some side unknown or with more than one real speed
    if uncertain and out and all(abs(o[0] - 1) > 1e-9 for o in out):
        out.append((1.0, None, None))  # same duration: standards conversion (e.g. native 29.97 -> 25)
    return out, uncertain


def pick_speed(cands, dr):
    """Picks the candidate whose ratio best matches the duration ratio; on a near tie, the order wins."""
    if dr is None or len(cands) == 1:
        return cands[0]
    errs = [abs(dr / c[0] - 1) for c in cands]
    m = min(errs)
    return next(c for c, e in zip(cands, errs) if e <= m + 0.0015)
