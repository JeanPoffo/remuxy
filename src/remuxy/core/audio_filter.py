"""ffmpeg audio filter that applies the timing model: speed change, delay/trim and padding to the video's end."""
from remuxy.core.constants import LAYOUT


def atempo_chain(speed):
    """atempo filters for `speed` (each atempo only accepts 0.5-2.0, so larger changes are chained)."""
    parts = []
    while speed > 2.0:
        parts.append("atempo=2.0")
        speed /= 2.0
    while speed < 0.5:
        parts.append("atempo=0.5")
        speed /= 0.5
    parts.append(f"atempo={speed:.9f}")
    return parts


def out_layout(codec, ch):
    """(forced channel layout or None, number of output channels) for `codec` and `ch` input channels."""
    if codec in ("ac3", "eac3") and ch > 6:
        return "5.1", 6  # ffmpeg's (E-)AC3 goes up to 5.1: explicit downmix, otherwise the LFE is lost
    if codec in ("aac", "libopus") and ch in LAYOUT:
        return LAYOUT[ch], ch  # without it AAC writes 5.1(side) as an "unknown" layout
    return None, ch


def splice(steps):
    """Filter fragment that cuts the stream at each (position, seconds) of `steps`: positive seconds insert that
    much silence at the position, negative ones drop that much audio from it. Positions are stream times."""
    pieces, start = [], 0.0
    for pos, d in steps:
        end = max(pos, start)
        if end - start > 0.0005 or not pieces:
            pieces.append([start, end, max(d, 0.0)])
        else:
            pieces[-1][2] += max(d, 0.0)  # empty piece (two cuts together): its silence goes on the previous one
        start = end + max(-d, 0.0)
    pieces.append([start, None, 0.0])
    n = len(pieces)
    parts = [f"asplit={n}" + "".join(f"[g{i}]" for i in range(n))]
    for i, (s, e, pad) in enumerate(pieces):
        x = f"[g{i}]atrim=start={s:.6f}" + (f":end={e:.6f}" if e is not None else "") + ",asetpts=PTS-STARTPTS"
        if pad > 0.0005:
            x += f",apad=pad_dur={pad:.6f}"  # silence in the stream's own format (no layout to match)
        parts.append(x + f"[h{i}]")
    parts.append("".join(f"[h{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1")
    return ";".join(parts)


def build_filter(a, b, a_s, ch, out_end, codec, sample_rate=None, src_sr=0, stretch="atempo", steps=None):
    """Audio filter that applies t_out = a + b * t_source and ends together with the video.
    `steps` (from --segments) splice the stream before the speed change; `a` is then the first stretch's delay.
    Returns (filter string, delay of the first audio sample in the output)."""
    steps = list(steps or [])
    while steps and steps[0][0] <= 0.0005:
        a += b * steps.pop(0)[1]  # a cut at the very start is just a different initial delay
    delay = a + b * a_s  # where the first audio sample lands on the output timeline
    f = ["asetpts=PTS-STARTPTS"]
    if codec != "copy":
        # async=1 fills timestamp gaps (missing packets in the source) with silence,
        # instead of "gluing" the audio and putting everything after the gap out of sync
        f.append("aresample=" + (f"{sample_rate}:" if sample_rate else "") + "async=1:first_pts=0")
    speed = []
    if abs(b - 1) > 1e-9:
        if stretch == "resample" and src_sr:
            # like a real PAL speedup: plays faster/slower and the pitch changes with it; exact, no artifacts.
            # asetrate only takes an integer rate: raise the rate by a multiple that makes rounding negligible
            m = min(range(1, 9), key=lambda q: abs(src_sr * q / b - round(src_sr * q / b)) / q)
            f[-1] = f"aresample={src_sr * m}:async=1:first_pts=0"
            speed = [f"asetrate={round(src_sr * m / b)}", f"aresample={sample_rate or src_sr}"]
        else:
            speed = atempo_chain(1.0 / b)  # keeps the pitch (WSOLA); each instant wobbles ~±15 ms
    if steps and codec != "copy":
        f.append(splice(steps))  # in source time: before the speed change
    f += speed
    if delay > 0.0005:
        # adelay keeps the timestamps of what came before it (atempo, aresample), so the encoder may see a jump
        # over the delay instead of the silence frames: the start of the track then has NO audio data and TVs
        # stall. Renumbering the timestamps by sample count makes the inserted silence real.
        f += ["adelay=" + "|".join([f"{delay * 1000:.1f}"] * ch), "asetpts=N/SR/TB"]
    elif delay < -0.0005:
        f += [f"atrim=start={-delay:.6f}", "asetpts=PTS-STARTPTS"]
    f += [f"apad=whole_dur={out_end:.3f}", f"atrim=end={out_end:.3f}"]
    lay, _ = out_layout(codec, ch)
    if lay:
        f.append(f"aformat=channel_layouts={lay}")
    return ",".join(f), delay
