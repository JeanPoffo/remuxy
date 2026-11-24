"""Output codec choice for the new track: resolves --codec auto/copy against speed changes and container rules,
and picks the output sample rate and channel count."""
from remuxy.core.audio_filter import out_layout
from remuxy.core.constants import AUTO_COPY, NO_COPY, SAME_CODEC
from remuxy.core.probe import num

# Copying without re-encoding shifts the packets: a positive delay leaves the start of the new track with
# NO audio data at all (not silence). Some TVs stall or start without sound on such a gap.
MAX_COPY_GAP = 0.5


def resolve_codec(args, sa, b, ch, delay=0.0, spliced=False):
    """Decides how the new track (source audio stream `sa`, `ch` channels, speed factor `b`, first sample landing
    at `delay` s on the output) is written. Returns (codec, output sample rate or 0, source sample rate, output channels); codec "copy" = no re-encode.
    `spliced` (--segments cut the audio) rules out a copy too."""
    codec = args.codec
    src_codec = sa.get("codec_name")
    src_sr = int(num(sa.get("sample_rate"), 0))
    if codec == "auto":
        reason = (f"{src_codec} has no guaranteed Direct Play on TVs" if src_codec not in AUTO_COPY
                  else f"speed adjustment ({1 / b:.5f}x)" if abs(b - 1) > 1e-9
                  else "spliced per stretch (--segments)" if spliced
                  else f"source at {src_sr} Hz (≠ {args.sample_rate} Hz)"
                  if args.sample_rate and src_sr != args.sample_rate else None)
        codec = ("aac" if not spliced or src_codec not in AUTO_COPY else SAME_CODEC[src_codec]) if reason else "copy"
        print(f"codec auto: {'copying ' + src_codec + ' without re-encoding' if codec == 'copy' else 're-encoding to aac: ' + reason}")
    if codec == "copy" and src_codec in NO_COPY:
        codec = NO_COPY[src_codec]
        print(f"WARNING: {src_codec} cannot be copied into MKV; using {codec} (lossless).")
    if codec == "copy" and abs(b - 1) > 1e-9:
        codec = SAME_CODEC.get(src_codec, "ac3" if ch > 2 else "aac")
        print(f"WARNING: --codec copy is impossible with a speed adjustment ({1 / b:.5f}x); re-encoding to {codec}.")
    if codec == "copy" and spliced:
        codec = SAME_CODEC.get(src_codec, "ac3" if ch > 2 else "aac")
        print(f"WARNING: --codec copy cannot splice the audio (--segments); re-encoding to {codec}.")
    if codec == "copy" and delay > MAX_COPY_GAP:
        if args.codec == "auto":
            codec = SAME_CODEC.get(src_codec, "ac3" if ch > 2 else "aac")
            print(f"codec auto: the new audio starts {delay:.3f}s in; re-encoding to {codec} so that stretch is "
                  "filled with silence (a copy would leave it with no audio data)")
        else:
            print(f"WARNING: with --codec copy the first {delay:.3f}s of the new track have no audio data; "
                  "some TVs stall or start without sound. Prefer --codec auto.")
    sr = args.sample_rate
    if codec == "libopus":
        sr = 48000  # Opus only exists at 48 kHz (and submultiples)
    elif codec in ("ac3", "eac3") and not sr and src_sr not in (32000, 44100, 48000):
        sr = 48000  # (E-)AC3 only accepts 32/44.1/48 kHz
    if codec == "copy" and args.sample_rate and src_sr and src_sr != args.sample_rate:
        print(f"WARNING: --codec copy keeps {src_sr} Hz (≠ {args.sample_rate} Hz); "
              "some TVs handle it badly. Prefer re-encoding.")
    _, ch_out = out_layout(codec, ch)
    if ch_out != ch:
        print(f"WARNING: {codec} goes up to 5.1; the {ch} channels will be downmixed to 5.1 "
              "(use --codec aac/flac to keep them).")
    return codec, sr, src_sr, ch_out
