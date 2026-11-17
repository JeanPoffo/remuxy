"""One-line file summary shown under the source/target fields: duration, video, audio tracks and subtitles.

On the source, the audio track that will be copied is highlighted and the others are dimmed.
"""
from __future__ import annotations

import json
import subprocess

from rich.text import Text

from remuxy.tui.theme import DIM, LILAC, ORANGE, RED, TEXT


def human(sec: float) -> str:
    """Seconds as M:SS, or H:MM:SS from one hour on."""
    sec = max(int(sec), 0)
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def probe_file(path: str) -> dict | Text:
    """ffprobe of the file (runs in a thread). Returns the JSON or an error Text."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                            path], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        info = json.loads(r.stdout or "{}")
    except Exception as e:  # noqa: BLE001
        return Text(f"could not read: {e}", style=RED)
    if r.returncode or not info.get("streams"):
        return Text("not a valid media file", style=RED)
    return info


def probe_summary(info: dict | Text, sel: int | None = None) -> Text:
    """Short summary of an already probed file. `sel` = chosen audio track: highlighted, the others dimmed."""
    if isinstance(info, Text):
        return info
    st = info["streams"]
    dur = float(info.get("format", {}).get("duration") or 0)
    parts: list[tuple[str, str]] = []
    v = next((s for s in st if s.get("codec_type") == "video"
              and not (s.get("disposition") or {}).get("attached_pic")), None)
    if v:
        try:
            n, d = (v.get("avg_frame_rate") or "0/1").split("/")
            fps = f"{int(n) / int(d):.3f}".rstrip("0").rstrip(".") if int(d) else "?"
        except ValueError:
            fps = "?"
        parts.append((f"{v.get('codec_name')} {v.get('width')}x{v.get('height')} @{fps}fps", TEXT))
    else:
        parts.append(("audio only", ORANGE))
    auds = [s for s in st if s.get("codec_type") == "audio"]
    shown = list(range(min(len(auds), 4)))
    if sel is not None and 4 <= sel < len(auds):
        shown[-1] = sel  # the chosen track is always shown, even beyond the first 4
    for i in shown:
        a = auds[i]
        lang = (a.get("tags") or {}).get("language", "")
        lay = a.get("channel_layout") or f"{a.get('channels')}ch"
        txt = f"#{i} {a.get('codec_name')} {lay}" + (f" {lang}" if lang and lang != "und" else "")
        if sel is None:
            parts.append((txt, LILAC))
        elif i == sel:
            parts.append((f"▶ {txt}", f"bold {LILAC}"))
        else:
            parts.append((txt, DIM))
    if len(auds) > len(shown):
        parts.append((f"+{len(auds) - len(shown)} audio", DIM if sel is not None else LILAC))
    if sel is not None and not 0 <= sel < len(auds):
        parts.append((f"track #{sel} does not exist", f"bold {RED}"))
    subs = sum(1 for s in st if s.get("codec_type") == "subtitle")
    if subs:
        parts.append((f"{subs} subtitle(s)", TEXT))
    out = Text(human(dur), style=ORANGE)
    for txt, sty in parts:
        out.append("  ·  ", style=DIM)
        out.append(txt, style=sty)
    return out
