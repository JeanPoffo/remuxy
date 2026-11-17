"""Output codec choice for the new track: resolves --codec auto/copy against speed changes and container rules,
and picks the output sample rate and channel count."""
from remuxy.core.audio_filter import out_layout
from remuxy.core.constants import AUTO_COPY, NO_COPY, SAME_CODEC
from remuxy.core.probe import num


def resolve_codec(args, sa, b, ch):
    """Decides how the new track (source audio stream `sa`, `ch` channels, speed factor `b`) is written.
    Returns (codec, output sample rate or 0, source sample rate, output channels); codec "copy" = no re-encode."""
    codec = args.codec
    src_codec = sa.get("codec_name")
    src_sr = int(num(sa.get("sample_rate"), 0))
    if codec == "auto":
        reason = (f"{src_codec} has no guaranteed Direct Play on TVs" if src_codec not in AUTO_COPY
                  else f"speed adjustment ({1 / b:.5f}x)" if abs(b - 1) > 1e-9
                  else f"source at {src_sr} Hz (≠ {args.sample_rate} Hz)"
                  if args.sample_rate and src_sr != args.sample_rate else None)
        codec = "aac" if reason else "copy"
        print(f"codec auto: {'copying ' + src_codec + ' without re-encoding' if codec == 'copy' else 're-encoding to aac: ' + reason}")
    if codec == "copy" and src_codec in NO_COPY:
        codec = NO_COPY[src_codec]
        print(f"WARNING: {src_codec} cannot be copied into MKV; using {codec} (lossless).")
    if codec == "copy" and abs(b - 1) > 1e-9:
        codec = SAME_CODEC.get(src_codec, "ac3" if ch > 2 else "aac")
        print(f"WARNING: --codec copy is impossible with a speed adjustment ({1 / b:.5f}x); re-encoding to {codec}.")
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
