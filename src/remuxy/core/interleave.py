"""Interleave check: confirms the new audio travels together with the video in the written file.

If the video runs many seconds ahead, small-buffer TVs stall at the start in Direct Play.
"""
from remuxy.core.probe import probe
from remuxy.core.process import run


def check_interleave(path, aidx, secs=300, limit=2.0):
    """Checks, in the file's physical order, whether audio #aidx travels together with the video
    over the first `secs` seconds, and prints the largest distance found (OK up to `limit` s)."""
    r = run(["ffprobe", "-v", "error", "-read_intervals", f"%+{secs}",
             "-show_entries", "packet=stream_index,pts_time",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    info = probe(path)["streams"]
    v_idx = next((s["index"] for s in info if s["codec_type"] == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    a_list = [s["index"] for s in info if s["codec_type"] == "audio"]
    if v_idx is None or aidx >= len(a_list):
        return
    a_idx, mv, ma, worst = a_list[aidx], None, None, 0.0
    for line in r.stdout.splitlines():
        p = line.split(",")
        if len(p) < 2 or p[1] in ("", "N/A"):
            continue
        try:
            si, t = int(p[0]), float(p[1])
        except ValueError:
            continue
        if si == v_idx:
            mv = t if mv is None else max(mv, t)
        elif si == a_idx:
            ma = t if ma is None else max(ma, t)
        if mv is not None and ma is not None:
            worst = max(worst, abs(mv - ma))
    if mv is None or ma is None:
        print("interleave: could not be checked (packets without timestamps)")
        return
    status = "OK" if worst <= limit else "PROBLEM: TVs may stall at the start"
    print(f"new audio x video interleave (first {secs}s): max distance {worst:.2f}s -> {status}")
