"""Builds the final ffmpeg command: stream mapping and order, track flags, codecs and metadata of the output.

The target's video, subtitles, attachments, chapters and original audio are copied; the new track is added
first and as default (or last with --append), laid out for Plex/TV Direct Play.
"""
from remuxy.core.constants import IMAGE_SUBS, KEEP_FLAGS, NO_COPY, SUB_COPY, SUB_TEXT
from remuxy.core.process import input_options


def without_default(stream):
    """-disposition value that removes only "default" and keeps the other flags (works on any ffmpeg)."""
    d = stream.get("disposition") or {}
    return "+".join(k for k in KEEP_FLAGS if d.get(k)) or "0"


def build_mux_command(args, src, tgt, sa, codec, flt, a, ch_out, tmp):
    """ffmpeg command that writes the output to `tmp`.
    Returns (cmd, index of the new track among the output audios, indexes of the original audios)."""
    copy = codec == "copy"
    # Audio order in the output: new track first (default) or after the originals (--append).
    origs = [] if args.replace else tgt.audios
    first = not args.append
    k = 0 if first else len(origs)                              # new track's index among the output audios
    orig_idx = [j + 1 if first else j for j in range(len(origs))]  # originals' indexes in the output
    make_default = args.default or first

    cmd = (["ffmpeg", "-hide_banner", "-nostdin", "-y"] + input_options(tgt.path) + ["-i", str(tgt.path)]
           + input_options(src.path))
    if copy and abs(a) > 0.0005:
        cmd += ["-itsoffset", f"{a:.6f}"]
    cmd += ["-i", str(src.path)]
    if copy:
        new_map = ["-map", f"1:a:{args.audio}"]
    else:
        cmd += ["-filter_complex", f"[1:a:{args.audio}]{flt}[new]"]
        new_map = ["-map", "[new]"]
    orig_map = ["-map", "0:a"] if origs else []
    # Main video only. Embedded cover art (cover.jpg etc.) shows up in ffprobe as an "attached_pic" video, and
    # "-map 0:v" would copy it as real MJPEG video tracks (ffmpeg loses the cover flag in MKV).
    maps = ["-map", f"0:{tgt.video['index']}"] + (new_map + orig_map if first else orig_map + new_map)
    sub_opts, n_sub = [], 0
    for s in tgt.subs:
        name, d = s.get("codec_name"), s.get("disposition") or {}
        if name in SUB_TEXT:
            sub_opts += [f"-c:s:{n_sub}", "srt"]  # MP4 subtitles cannot be copied into MKV
        elif name not in SUB_COPY:
            print(f"WARNING: subtitle #{s.get('index')} ({name or 'unknown'}) is not supported in MKV; left out.")
            continue
        maps += ["-map", f"0:{s['index']}"]
        if not args.keep_sub_default and name in IMAGE_SUBS and d.get("default"):
            sub_opts += [f"-disposition:s:{n_sub}", without_default(s)]
        n_sub += 1
    maps += ["-map", "0:t?"]
    # chapters and global metadata always come from the TARGET (otherwise, if only the source had chapters,
    # ffmpeg would use them).
    # -max_interleave_delta 0: the muxer waits for the filtered audio instead of dumping video ahead of it.
    # Without it the new audio ends up "late" in the file (e.g. 37 s of audio only at 24 MB) and players
    # with a small buffer (Samsung TVs on Direct Play) stall during the first seconds.
    cmd += maps + ["-map_chapters", "0", "-map_metadata", "0",
                   "-c:v", "copy", "-c:s", "copy", "-c:t", "copy", "-max_interleave_delta", "0"] + sub_opts
    for j, s in zip(orig_idx, origs):
        if s.get("codec_name") in NO_COPY:
            print(f"WARNING: original audio #{j} ({s['codec_name']}) cannot be copied into MKV; "
                  f"converted to {NO_COPY[s['codec_name']]} (lossless).")
            cmd += [f"-c:a:{j}", NO_COPY[s["codec_name"]]]
        else:
            cmd += [f"-c:a:{j}", "copy"]
        if make_default and (s.get("disposition") or {}).get("default"):
            cmd += [f"-disposition:a:{j}", without_default(s)]
    if copy:
        cmd += [f"-c:a:{k}", "copy", f"-copypriorss:a:{k}", "0"]
    else:
        cmd += [f"-c:a:{k}", codec]
        if codec != "flac":
            cmd += [f"-b:a:{k}", args.bitrate or f"{min(96 * ch_out, 640)}k"]
    lang = args.lang or (sa.get("tags") or {}).get("language") or "und"
    title = args.title or (sa.get("tags") or {}).get("title")
    cmd += [f"-metadata:s:a:{k}", f"language={lang}"]
    if title:
        cmd += [f"-metadata:s:a:{k}", f"title={title}"]
    cmd += [f"-disposition:a:{k}", "default" if make_default else "0"]
    if codec in ("libopus", "flac"):
        print(f"WARNING: {codec} may not Direct Play on TVs (Samsung/LG); aac/ac3/eac3 are safer.")
    cmd += ["-f", "matroska", str(tmp)]
    return cmd, k, orig_idx
