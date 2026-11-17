"""Track: a whole audio track decoded once and reduced to the two envelope curves the auto-sync correlates.

`get_track` caches them, so each track is decoded only once per run.
"""
import sys

from remuxy.core.constants import CENTER, ENV_HZ, ENV_SR
from remuxy.core.process import input_options, run

_TRACKS = {}


class Track:
    """Whole audio track reduced to two curves at ENV_HZ points/s, aligned to the file's timeline
    (index 0 = start of the file; timestamp gaps become silence):
      env = log energy envelope minus its slow trend -> wide peak, tolerates small speed differences
      on  = "attacks" (sudden energy rises)            -> sharp peak, finds the alignment even with different dialogue
    """

    def __init__(self, media, aidx):
        import numpy as np
        s = media.audios[aidx]
        base = (["ffmpeg", "-v", "error", "-nostdin"] + input_options(media.path)
                + ["-i", str(media.path), "-map", f"0:a:{aidx}", "-vn", "-sn", "-dn"])
        res = f"aresample={ENV_SR}:async=1:first_pts=0"
        x = None
        self.no_center = False
        if s.get("channel_layout") in CENTER:
            r = run(base + ["-af", f"pan=stereo|c0=0.5*FL+0.5*FR|c1=FC,{res}", "-f", "s16le", "-"], capture_output=True)
            if r.returncode == 0 and len(r.stdout) >= 4:
                y = np.frombuffer(r.stdout[: len(r.stdout) // 4 * 4], dtype=np.int16).reshape(-1, 2).astype(np.float32)
                sides, center = y[:, 0], y[:, 1]
                # old "5.1" movie with everything in the center: the sides are near silence and useless as reference
                if float(np.sqrt(np.mean(sides ** 2))) >= 0.1 * float(np.sqrt(np.mean(center ** 2))):
                    x, self.no_center = sides, True
                else:
                    x = sides + center
        if x is None:
            r = run(base + ["-af", res, "-ac", "1", "-f", "s16le", "-"], capture_output=True)
            if r.returncode or len(r.stdout) < 2:
                sys.exit(f"failed to decode the audio of {media.path}:\n"
                         f"{r.stderr.decode(errors='replace').strip()[:500]}")
            x = np.frombuffer(r.stdout[: len(r.stdout) // 2 * 2], dtype=np.int16).astype(np.float32)
        self.dur = len(x) / ENV_SR
        k = ENV_SR // ENV_HZ
        e = np.log1p(np.abs(x[: len(x) // k * k]).reshape(-1, k).mean(axis=1)).astype(np.float64)
        self.on = np.maximum(np.diff(e, prepend=e[:1]), 0.0) if len(e) else e
        w = 2 * ENV_HZ  # 2 s moving average
        if len(e) > 2 * w:
            c = np.cumsum(np.insert(e, 0, 0.0))
            m = (c[w:] - c[:-w]) / w
            e = e - np.concatenate([np.full(w // 2, m[0]), m, np.full(len(e) - len(m) - w // 2, m[-1])])
        self.env = e

    def feats(self):
        """The two curves compared by the correlation, in a fixed order."""
        return (self.env, self.on)


def get_track(media, aidx):
    """Decoded Track for audio #aidx of `media`, from the cache when already decoded."""
    key = (str(media.path), aidx)
    if key not in _TRACKS:
        print(f"  decoding audio #{aidx} of {media.path.name}...", flush=True)
        _TRACKS[key] = Track(media, aidx)
    return _TRACKS[key]
