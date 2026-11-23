"""pick_sync_track: chooses which SOURCE audio track --auto-sync measures against the target.

The measurement does not need to use the track being copied: every track of a file shares the same
timeline, so the alignment measured with one of them holds for all of them. A dub compared with the
original audio only matches on music/effects (the dialogue differs, and on stereo it cannot be left out),
which can make the measurement weak or inconclusive. When the source also carries the target's original
language (e.g. a dubbed release that keeps the original track), comparing like with like is far stronger.
"""

UNKNOWN = {"", "und", "unk", "mis", "zxx"}


def _lang(stream):
    """Lower-cased language tag of a stream, or "" when missing/undetermined."""
    lang = ((stream.get("tags") or {}).get("language") or "").strip().lower()
    return "" if lang in UNKNOWN else lang


def pick_ref_track(src, tgt, args):
    """Index of the TARGET audio track --auto-sync measures against, and a note explaining the choice (or None).

    Releases often put foreign dubs first (e.g. Russian voice-overs before the original Japanese); measuring
    against one of those compares different dialogue and can come out inconclusive. Without --ref-audio, the
    first target track in a language the source also has is used, preferring one other than --audio's (the
    original rather than the dub); with no language in common, track 0.
    """
    if args.ref_audio is not None:
        return args.ref_audio, None
    have = {_lang(s) for s in src.audios} - {""}
    dub = _lang(src.audios[args.audio])
    common = [i for i, t in enumerate(tgt.audios) if _lang(t) in have]
    pick = next((i for i in common if _lang(tgt.audios[i]) != dub), common[0] if common else 0)
    if pick == 0:
        return 0, None
    return pick, (f"reference: target track #{pick} ({_lang(tgt.audios[pick])}, a language the source also has); "
                  "use --ref-audio to choose another")


def pick_sync_track(src, tgt, args):
    """Index of the SOURCE audio track to measure with, and a note explaining the choice (or None).

    --sync-audio forces the track. Otherwise, when the chosen track's language differs from the target
    reference's and another source track has the reference's language, that track is used.
    """
    if args.sync_audio is not None:
        if args.sync_audio == args.audio:
            return args.audio, None
        return args.sync_audio, f"measuring with source track #{args.sync_audio} (--sync-audio)"
    ref = _lang(tgt.audios[args.ref_audio])
    if not ref or _lang(src.audios[args.audio]) == ref:
        return args.audio, None
    for i, s in enumerate(src.audios):
        if i != args.audio and _lang(s) == ref:
            return i, (f"measuring with source track #{i} ({ref}, same language as the target reference); "
                       f"the result applies to track #{args.audio} (same file, same timeline). "
                       f"Use --sync-audio {args.audio} to measure with the new track itself")
    return args.audio, None
