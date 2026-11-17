"""Whole-movie correlation: for each candidate speed, finds the overall delay with no search limit.

This is the first auto-sync pass; its peak strength also confirms (or corrects) the predicted speed.
"""
from remuxy.core.constants import ENV_HZ
from remuxy.core.correlation import zscore


def coarse(S, T, bs):
    """Whole-movie correlation for each candidate speed factor b.
    Returns [(b, a, z)]: a = where the source start lands in the target; z = peak prominence (>= 8 is significant)."""
    import numpy as np
    hz, nt, out = ENV_HZ, len(T.env), []
    if nt < 20 * hz or len(S.env) < 20 * hz:
        return out
    nfft = 1 << (nt + int(len(S.env) * max(bs)) + 1).bit_length()
    FT = [np.fft.rfft(zscore(f), nfft) for f in T.feats()]
    for b in bs:
        m = int(len(S.env) * b)
        minov = max(int(0.3 * min(m, nt)), 10 * hz)
        if minov > min(m, nt):
            continue
        tot = None
        for fs, F in zip(S.feats(), FT):
            p = np.interp(np.arange(m) / b, np.arange(len(fs)), fs)
            if p.std() < 1e-9:
                continue
            c = np.fft.irfft(F * np.conj(np.fft.rfft(zscore(p), nfft)), nfft)
            cc = np.concatenate([c[nfft - (m - 1):], c[:nt]])[minov - 1: m + nt - minov]  # lags -(m-minov)..nt-minov
            cc = cc / (cc.std() + 1e-12)
            tot = cc if tot is None else tot + cc
        if tot is None:
            continue
        k = int(np.argmax(tot))
        z = float((tot[k] - np.median(tot)) / (tot.std() + 1e-12))
        out.append((b, (k - (m - minov)) / hz, z))
    return out
