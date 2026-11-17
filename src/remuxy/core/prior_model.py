"""Metadata timing model: t_target = a + b * t_source, from stream start times, fps and durations.

Used as-is without --auto-sync, and as the starting point (and speed candidates) for the measurement.
"""
from remuxy.core.constants import FILM
from remuxy.core.speed import pick_speed, speed_candidates, true_rates


def prior_model(src, tgt, args):
    """t_target = a + b * t_source (each file's normalized times).
    Returns (a, b, notes to print, alternative speeds for --auto-sync to also test)."""
    sa = src.audios[args.audio]
    vs = src.rel_start(src.video) if src.video else 0.0
    vt = tgt.rel_start(tgt.video)
    ds = src.duration(src.video) if src.video else src.duration(sa)
    dt = tgt.duration(tgt.video)
    dr = dt / ds if ds and dt else None
    b, notes, alts = 1.0, [], []
    if args.speed:
        b = 1.0 / args.speed
        notes.append(f"manual speed {args.speed}x")
    elif args.no_tempo:
        notes.append("speed adjustment disabled (--no-tempo)")
    else:
        S, T = true_rates(src.fps()), true_rates(tgt.fps())
        for name, m, R in (("SOURCE", src, S), ("TARGET", tgt, T)):
            if m.video and not R:
                raw = m.raw_fps()
                notes.append(f"{name}: fps {'unknown' if not raw else f'{float(raw):.3f} non-standard'} "
                             "(VFR/mixed telecine?): speed deduced from the duration")
            elif len(R) > 1:
                notes.append(f"{name} reports {float(m.fps()):.3f} fps (NTSC DVD pulldown/interlaced?): "
                             f"considering the possible real speeds {[round(float(x), 3) for x in R]}")
        cands, uncertain = speed_candidates(S, T)
        guess = uncertain or len(cands) > 1  # there is a choice to make: only trust it if the duration confirms
        if not cands:
            notes.append(f"WARNING: incompatible fps ({float(src.fps() or 0):.3f} vs {float(tgt.fps() or 0):.3f}); "
                         "no speed adjustment (use --auto-sync or --speed)")
        elif guess and dr is None:
            notes.append("WARNING: no durations to choose the speed; no adjustment (use --auto-sync or --speed)")
        else:
            b, rs, rt = pick_speed(cands, dr)
            err = abs(dr / b - 1) if dr else 0.0
            if guess and err > 0.01:
                # no known combination explains the duration difference: do not risk stretching
                notes.append(f"WARNING: duration ratio {dr:.5f} ({ds:.1f}s -> {dt:.1f}s) matches no known "
                             "fps combination; no speed adjustment. Probably different cuts "
                             "-> use --auto-sync or --offset")
                b = 1.0
            else:
                if rs is None:
                    notes.append("equal durations despite different fps (standards conversion): "
                                 "no speed adjustment")
                elif abs(b - 1) > 1e-9:
                    notes.append(f"speed: content {float(rs):.3f} -> {float(rt):.3f} fps"
                                 + (f" (duration ratio {dr:.5f})" if dr else "")
                                 + f": audio plays at {1 / b:.5f}x")
                    if dr and err > 0.01:
                        notes.append(f"WARNING: durations ({ds:.1f}s vs {dt:.1f}s) do not match the fps ratio; "
                                     "there may be different cuts -> use --auto-sync and check")
                if abs(b - 1) <= 1e-9 and dr and abs(dt - ds) > 0.5:
                    notes.append(f"WARNING: same speed but different durations ({ds:.1f}s vs {dt:.1f}s, "
                                 f"{dt - ds:+.1f}s). Probably different cuts (logos/extra scenes). "
                                 "Use --auto-sync to measure the offset, or a manual --offset")
                if guess and dr:
                    close = [c for c in cands if abs(c[0] - b) > 1e-9
                             and abs(dr / c[0] - 1) <= err + 0.0015]
                    if close:
                        notes.append("AMBIGUOUS: the durations cannot tell apart the speeds "
                                     + " / ".join(f"{1 / x:.5f}x" for x in [b] + [c[0] for c in close])
                                     + f" (chose {1 / b:.5f}x; e.g. 23.976 vs 24 fps); "
                                     "confirm with --auto-sync --verify")
                if guess:
                    notes.append("speed deduced from the duration (not the fps): worth confirming with --auto-sync --verify")
        # speeds the --auto-sync also tests: every 23.976/24/25 film combination and "no adjustment"
        alts = sorted({float(x / y) for x in FILM for y in FILM} | {c[0] for c in cands}, key=lambda v: abs(v - b))
    a = vt - vs * b + args.offset
    return a, b, notes, alts
