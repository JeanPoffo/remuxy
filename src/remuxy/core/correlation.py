"""Window correlation: finds where a short stretch of the source audio lands in the target audio.

Normalized FFT cross-correlation of both envelope curves, refined to sub-sample precision.
"""
from remuxy.core.constants import ENV_HZ


def cut(f, i, n):
    """f[i:i+n], zero-filled where it falls outside the array."""
    import numpy as np
    out = np.zeros(n)
    lo, hi = max(i, 0), min(i + n, len(f))
    if hi > lo:
        out[lo - i: hi - i] = f[lo:hi]
    return out


def zscore(v):
    """v standardized to mean 0 and standard deviation 1."""
    return (v - v.mean()) / (v.std() + 1e-9)


def measure_point(S, T, ts, a0, b0, win, search):
    """For the source stretch [ts, ts+win], finds where it lands in the target.
    Returns (ts, u, correlation): u = target time matching ts. None when there is no comparable audio."""
    import numpy as np
    hz = ENV_HZ
    i, n = int(round(ts * hz)), int(win * hz)
    ts = i / hz
    m = int(n * b0)                                   # stretch length in target time
    j = int(round((a0 + b0 * ts - search) * hz))      # start of the search in the target
    L = m + int(2 * search * hz)
    if n < 5 * hz or i < 0 or i + n > len(S.env) + hz or j + L <= 0 or j >= len(T.env):
        return None
    tot, used = np.zeros(L - m + 1), 0
    for fs, ft in zip(S.feats(), T.feats()):
        p = cut(fs, i, n)
        p = np.interp(np.arange(m) / b0, np.arange(n), p)  # compensates the expected speed
        seg = cut(ft, j, L)
        if p.std() < 1e-9 or seg.std() < 1e-9:
            continue
        p, seg = zscore(p), seg - seg.mean()
        nfft = 1 << (L + m - 1).bit_length()
        c = np.fft.irfft(np.fft.rfft(seg, nfft) * np.conj(np.fft.rfft(p, nfft)), nfft)[: L - m + 1]
        e2 = np.cumsum(np.insert(seg ** 2, 0, 0.0))
        loc = np.maximum(e2[m:] - e2[:-m], 0.0)[: L - m + 1]
        tot += c / (np.sqrt(loc * float(np.sum(p ** 2))) + 1e-9)
        used += 1
    if not used:
        return None
    tot /= used
    k = int(np.argmax(tot))
    frac = 0.0  # sub-sample refinement (parabola through the 3 points around the peak)
    if 0 < k < len(tot) - 1:
        y0, y1, y2 = tot[k - 1], tot[k], tot[k + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            frac = float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5))
    return ts, (j + k + frac) / hz, float(tot[k])
