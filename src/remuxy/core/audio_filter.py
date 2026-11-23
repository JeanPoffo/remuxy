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


def build_filter(a, b, a_s, ch, out_end, codec, sample_rate=None, src_sr=0, stretch="atempo"):
    """Audio filter that applies t_out = a + b * t_source and ends together with the video.
    Returns (filter string, delay of the first audio sample in the output)."""
    delay = a + b * a_s  # where the first audio sample lands on the output timeline
    f = ["asetpts=PTS-STARTPTS"]
    if codec != "copy":
        # async=1 fills timestamp gaps (missing packets in the source) with silence,
        # instead of "gluing" the audio and putting everything after the gap out of sync
        f.append("aresample=" + (f"{sample_rate}:" if sample_rate else "") + "async=1:first_pts=0")
    if abs(b - 1) > 1e-9:
        if stretch == "resample" and src_sr:
            # like a real PAL speedup: plays faster/slower and the pitch changes with it; exact, no artifacts.
            # asetrate only takes an integer rate: raise the rate by a multiple that makes rounding negligible
            m = min(range(1, 9), key=lambda q: abs(src_sr * q / b - round(src_sr * q / b)) / q)
            f[-1] = f"aresample={src_sr * m}:async=1:first_pts=0"
            f += [f"asetrate={round(src_sr * m / b)}", f"aresample={sample_rate or src_sr}"]
        else:
            f += atempo_chain(1.0 / b)  # keeps the pitch (WSOLA); each instant wobbles ~±15 ms
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
