"""RemuxY: the main screen of the terminal UI.

Builds the `remux` command line from the form, runs it as a subprocess, turns ffmpeg's status line into a
progress bar with ETA, colors the log and handles cancel/quit (the partial file is cleaned up by `remux`).
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Input, Label, ProgressBar, RichLog, Select, Static

from remuxy import __version__ as VERSION
from remuxy.tui.file_picker import PickFile
from remuxy.tui.summary import human, probe_file, probe_summary
from remuxy.tui.theme import (APP_CSS, DIM, FF_SPEED, FF_STAT, FF_TIME, GREEN, LILAC, LOG_STYLES, ORANGE, RED,
                              TEXT, THEME)

# The `remux` CLI is run as `python -m remuxy.remux` with this package importable (installed or from source).
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CLI_MODULE = "remuxy.remux"


class RemuxY(App):
    """Form with the files and every `remux` option, a progress panel and the ffmpeg log."""

    TITLE = "remuxy"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+r", "start", "Start", priority=True),
        Binding("ctrl+t", "dry", "Dry-run", priority=True),
        Binding("ctrl+k", "cancel", "Cancel", priority=True),
        Binding("ctrl+f", "pick('src')", "Source", priority=True),
        Binding("ctrl+g", "pick('dst')", "Target", priority=True),
        Binding("ctrl+o", "pick('out')", "Output", priority=True),
        Binding("ctrl+l", "clear_log", "Clear log"),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    cancelled = False

    def __init__(self, src: str = "", dst: str = "") -> None:
        super().__init__()
        self.init_src, self.init_dst = src, dst
        self.proc: asyncio.subprocess.Process | None = None
        self.total = 0.0
        self.last_dir = Path.cwd()
        self.probed: dict[str, dict | Text] = {}  # ffprobe of source/target, to redraw the summary

    # ---------------------------------------------------------------- layout
    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("↪remuxy [#6d7092]" + VERSION + "[/]", id="brand")
            yield Static("Remux", id="tab")
            yield Static("Dub → movie", id="tab2")
            yield Static("", id="instance")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                with Vertical(id="files", classes="box") as files:
                    files.border_title = "Files"
                    files.border_subtitle = "^f source · ^g target · ^o output"
                    for key, label, ph in (("src", "Source", "movie or audio file the dub comes from"),
                                           ("dst", "Target", "movie that receives the audio"),
                                           ("out", "Output", "default: <target>.synced.mkv")):
                        with Horizontal(classes="row"):
                            yield Label(label, classes="lbl")
                            yield Input(placeholder=ph, id=f"{key}", classes="path")
                            yield Button("…", id=f"pick-{key}", classes="pick")
                        yield Static("", id=f"{key}-info", classes="info")
                with Horizontal(id="actions"):
                    yield Button("▶ Start", id="start")
                    yield Button("Dry-run", id="dry")
                    yield Button("■ Cancel", id="cancel", disabled=True)
                    yield Static("^r start · ^t dry-run · ^k cancel", id="actions-hint")
            with Vertical(id="opts", classes="box") as opts:
                opts.border_title = "Options"
                with VerticalScroll(id="opts-scroll"):
                    yield Label("Sync", classes="sec sec-first")
                    with Horizontal(classes="checks"):
                        with Vertical():
                            yield Checkbox("auto-sync", True, id="auto_sync", tooltip="measures the real delay (numpy)")
                            yield Checkbox("verify", True, id="verify", tooltip="checks the result at the end")
                        with Vertical():
                            yield Checkbox("no-tempo", id="no_tempo", tooltip="no speed correction from the fps")
                            yield Checkbox("overwrite", True, id="overwrite",
                                           tooltip="overwrites the output file if it already exists")
                    yield from self.opt("Offset (s)", "offset", "0.0  (+ delays, - advances)", "number")
                    yield from self.opt("Speed", "speed", "automatic  (e.g. 1.04271)", "number")
                    with Horizontal(classes="opt"):
                        yield Label("Stretch", classes="opt-l")
                        yield Select([("atempo (keeps pitch)", "atempo"),
                                      ("resample (exact, shifts pitch)", "resample")],
                                     value="atempo", allow_blank=False, id="stretch")

                    yield Label("New track", classes="sec")
                    with Horizontal(classes="opt"):
                        yield Label("Codec", classes="opt-l")
                        yield Select([(c, c) for c in ("auto", "aac", "ac3", "eac3", "libopus", "flac", "copy")],
                                     value="auto", allow_blank=False, id="codec",
                                     tooltip="auto: copies AAC/AC3/E-AC3 without re-encoding when there is no "
                                             "speed adjustment; otherwise re-encodes to AAC")
                    yield from self.opt("Bitrate", "bitrate", "auto  (96k/channel, e.g. 640k)")
                    yield from self.opt("Sample rate", "sample_rate", "48000  (0 = source's)", "integer")
                    yield from self.opt("Language", "lang", "source's  (e.g. por)")
                    yield from self.opt("Title", "title", "source's  (e.g. Portuguese 5.1)")
                    yield from self.opt("Source track", "audio", "0", "integer")
                    with Horizontal(classes="checks"):
                        with Vertical():
                            yield Checkbox("append", id="append", tooltip="new track after the originals")
                            yield Checkbox("default", id="default", tooltip="marks the new track as default")
                        with Vertical():
                            yield Checkbox("replace", id="replace", tooltip="removes the original audio tracks")
                            yield Checkbox("keep-sub-default", id="keep_sub_default",
                                           tooltip="keeps the default flag on VOBSUB/PGS")

                    yield Label("Measurement", classes="sec")
                    yield from self.opt("Ref. track", "ref_audio", "0  (target audio)", "integer")
                    yield from self.opt("Sync track", "sync_audio", "auto  (source audio)", "integer")
                    yield from self.opt("Points", "points", "12", "integer")
                    yield from self.opt("Window (s)", "window", "120", "number")
                    yield from self.opt("Search ± (s)", "search", "30", "number")
                    yield from self.opt("Min score", "min_score", "0.03", "number")
        with Vertical(id="progress-box", classes="box") as pb:
            pb.border_title = "Progress"
            with Horizontal(id="status"):
                yield Static("ready", id="phase")
                yield Static("", id="eta")
            yield ProgressBar(total=100, show_eta=False, id="bar")
        with Vertical(id="log-box", classes="box") as lb:
            lb.border_title = "ffmpeg log"
            yield RichLog(id="log", wrap=True, highlight=False, markup=False, max_lines=5000)
        yield Footer()

    @staticmethod
    def opt(label: str, wid: str, ph: str, typ: str = "text"):
        """One labeled option input of the Options panel."""
        with Horizontal(classes="opt"):
            yield Label(label, classes="opt-l")
            yield Input(placeholder=ph, id=wid, type=typ)

    def on_mount(self) -> None:
        self.register_theme(THEME)
        self.theme = "remuxy"
        self.query_one("#bar", ProgressBar).update(total=100, progress=0)
        self.check_env()
        if self.init_src:
            self.set_path("src", self.init_src)
        if self.init_dst:
            self.set_path("dst", self.init_dst)
        self.query_one("#src", Input).focus()

    @work(thread=True)
    def check_env(self) -> None:
        """Shows the ffmpeg version and missing dependencies in the top bar."""
        msg = []
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
            m = re.search(r"version (\S+)", r.stdout)
            msg.append(f"ffmpeg {m[1].split('-')[0] if m else '?'}")
        except FileNotFoundError:
            msg.append(f"[{RED}]ffmpeg not found[/]")
        if importlib.util.find_spec("numpy") is None:
            msg.append(f"[{ORANGE}]no numpy: auto-sync/verify unavailable[/]")
        self.call_from_thread(self.query_one("#instance", Static).update, "  ·  ".join(msg))

    # ---------------------------------------------------------------- files
    def set_path(self, key: str, path: str) -> None:
        self.query_one(f"#{key}", Input).value = path

    @on(Input.Changed, "#src, #dst")
    def path_changed(self, ev: Input.Changed) -> None:
        key = ev.input.id
        p = Path(ev.value.strip()).expanduser()
        info = self.query_one(f"#{key}-info", Static)
        self.probed.pop(key, None)
        if not ev.value.strip():
            info.update("")
        elif p.is_file():
            self.last_dir = p.parent
            info.update(Text("reading…", style=DIM))
            self.summarize(key, str(p))
        else:
            info.update(Text("file not found", style=RED))
        if key == "dst":
            out = self.query_one("#out", Input)
            out.placeholder = (str(p.with_name(p.stem + ".synced.mkv")) if p.name
                               else "default: <target>.synced.mkv")

    @work(thread=True, group="probe")
    def summarize(self, key: str, path: str) -> None:
        info = probe_file(path)
        cur = self.query_one(f"#{key}", Input).value.strip()
        if Path(cur).expanduser() == Path(path):
            self.call_from_thread(self.show_summary, key, info)

    def show_summary(self, key: str, info: dict | Text) -> None:
        self.probed[key] = info
        self.refresh_summary(key)

    def refresh_summary(self, key: str) -> None:
        """Redraws a file summary; on the source, highlights the track set in "Source track" (default 0)."""
        info = self.probed.get(key)
        if info is None:
            return
        sel = None
        if key == "src":
            raw = self.query_one("#audio", Input).value.strip()
            try:
                sel = int(raw) if raw else 0
            except ValueError:
                sel = 0
        self.query_one(f"#{key}-info", Static).update(probe_summary(info, sel))

    @on(Input.Changed, "#audio")
    def audio_changed(self) -> None:
        self.refresh_summary("src")

    @on(Button.Pressed, ".pick")
    def pick_pressed(self, ev: Button.Pressed) -> None:
        self.action_pick(ev.button.id.removeprefix("pick-"))

    def action_pick(self, key: str) -> None:
        if self.proc:
            return
        titles = {"src": "Source: where the audio comes from", "dst": "Target: movie that receives the audio",
                  "out": "Output: choose the folder and type the name"}
        cur = self.query_one(f"#{key}", Input).value.strip()
        start = Path(cur).expanduser().parent if cur and Path(cur).expanduser().parent.is_dir() else self.last_dir

        def done(path: str | None) -> None:
            if path:
                self.set_path(key, path)

        self.push_screen(PickFile(titles[key], start, save=(key == "out")), done)

    # ---------------------------------------------------------------- running
    def build_args(self, dry: bool) -> list[str] | None:
        """Command line for the `remux` subprocess from the form, or None (with a notice) if incomplete."""
        val = lambda i: self.query_one(f"#{i}", Input).value.strip()  # noqa: E731
        chk = lambda i: self.query_one(f"#{i}", Checkbox).value  # noqa: E731
        src, dst, out = val("src"), val("dst"), val("out")
        for name, p in (("source", src), ("target", dst)):
            if not p:
                self.notify(f"Choose the {name} file.", severity="error")
                return None
            if not Path(p).expanduser().is_file():
                self.notify(f"{name.capitalize()} file not found.", severity="error")
                return None
        args = [sys.executable, "-u", "-m", CLI_MODULE, str(Path(src).expanduser()), str(Path(dst).expanduser())]
        if out:
            args += ["-o", str(Path(out).expanduser())]
        for wid, flag in (("auto_sync", "--auto-sync"), ("verify", "--verify"), ("no_tempo", "--no-tempo"),
                          ("overwrite", "--overwrite"), ("append", "--append"), ("default", "--default"),
                          ("replace", "--replace"), ("keep_sub_default", "--keep-sub-default")):
            if chk(wid) and not (dry and wid == "verify"):
                args.append(flag)
        for wid, flag in (("offset", "--offset"), ("speed", "--speed"), ("bitrate", "--bitrate"),
                          ("sample_rate", "--sample-rate"), ("lang", "--lang"), ("title", "--title"),
                          ("audio", "--audio"), ("ref_audio", "--ref-audio"), ("sync_audio", "--sync-audio"),
                          ("points", "--points"),
                          ("window", "--window"), ("search", "--search"), ("min_score", "--min-score")):
            if val(wid):
                args += [flag, val(wid)]
        for wid, flag, default in (("codec", "--codec", "auto"), ("stretch", "--stretch", "atempo")):
            v = self.query_one(f"#{wid}", Select).value
            if v != default:
                args += [flag, str(v)]
        if dry:
            args.append("--dry-run")
        return args

    def action_start(self) -> None:
        self.launch(dry=False)

    def action_dry(self) -> None:
        self.launch(dry=True)

    @on(Button.Pressed, "#start")
    def start_pressed(self) -> None:
        self.launch(dry=False)

    @on(Button.Pressed, "#dry")
    def dry_pressed(self) -> None:
        self.launch(dry=True)

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def launch(self, dry: bool) -> None:
        if self.proc:
            self.notify("A remux is already running.", severity="warning")
            return
        args = self.build_args(dry)
        if args:
            self.run_job(args, dry)

    def set_running(self, on_: bool) -> None:
        self.query_one("#start", Button).disabled = on_
        self.query_one("#dry", Button).disabled = on_
        self.query_one("#cancel", Button).disabled = not on_
        for w in self.query(".pick"):
            w.disabled = on_

    def phase(self, text: str, color: str = TEXT) -> None:
        self.query_one("#phase", Static).update(Text(text, style=color))

    def write(self, line: str) -> None:
        """Appends a line to the log, colored by LOG_STYLES; ffmpeg's metadata details are dimmed."""
        style = next((s for rx, s in LOG_STYLES if rx.search(line)), None)
        if style is None and (line[:1].isspace() and not line.lstrip().startswith(("t=", "-", "+", "1", "2", "3",
                                                                                     "4", "5", "6", "7", "8", "9"))
                              or line.startswith(("Input #", "Output #", "Stream mapping", "Press [q]"))):
            style = DIM  # ffmpeg details (metadata, streams): dimmed so the warnings stand out
        self.query_one("#log", RichLog).write(Text(line, style=style or TEXT))

    @work(exclusive=True, group="job")
    async def run_job(self, args: list[str], dry: bool) -> None:
        """Runs `remux`, streaming its output to the log and ffmpeg's progress to the bar."""
        log = self.query_one("#log", RichLog)
        bar = self.query_one("#bar", ProgressBar)
        eta = self.query_one("#eta", Static)
        log.write(Text(f"\n$ remux {shlex.join(args[4:])}", style=f"bold {LILAC}"))
        self.set_running(True)
        self.total, muxing, last_stat = 0.0, False, ""
        bar.update(total=None)
        eta.update("")
        self.phase("analyzing the files…", LILAC)
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "AV_LOG_FORCE_NOCOLOR": "1",
               "PYTHONPATH": os.pathsep.join(filter(None, [str(PACKAGE_ROOT), os.environ.get("PYTHONPATH")]))}
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *args, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, start_new_session=True, env=env)
        except OSError as e:
            self.write(f"ERROR starting: {e}")
            self.set_running(False)
            self.phase("failed to start", RED)
            return
        buf = b""
        while True:
            chunk = await self.proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            # ffmpeg updates its status line with \r; remux uses \n
            parts = re.split(rb"[\r\n]", buf)
            buf = parts.pop()
            for raw in parts:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                if FF_STAT.match(line):
                    m = FF_TIME.search(line)
                    if m and "time=N/A" not in line:
                        last_stat = line.strip()
                    if m and muxing and self.total > 0:
                        t = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
                        pct = min(max(t / self.total * 100, 0), 99.9)
                        bar.update(total=100, progress=pct)
                        sp = FF_SPEED.search(line)
                        if sp and float(sp[1]) > 0:
                            eta.update(Text(f"{human(t)} / {human(self.total)}  ·  {sp[1]}x  ·  "
                                            f"~{human((self.total - t) / float(sp[1]))} left", style=DIM))
                    continue
                self.write(line)
                self.track_phase(line)
                if line.startswith("$ ffmpeg"):
                    muxing = not dry
                    if muxing:
                        bar.update(total=100, progress=0)
                        self.phase("remux in progress (ffmpeg)…", ORANGE)
                if line.startswith("OK:"):
                    muxing = False
                    if last_stat:
                        self.write(last_stat)
                    bar.update(total=100, progress=100)
                    self.phase("checking the result…", LILAC)
                    if "--verify" in args:
                        bar.update(total=None)
        rc = await self.proc.wait()
        self.proc = None
        self.set_running(False)
        if rc == 0:
            bar.update(total=100, progress=100)
            self.phase("dry-run done: check the analysis in the log" if dry else "done ✓", GREEN)
            self.notify("Dry-run done." if dry else "Remux done.", title="remuxy")
        elif rc == 2:
            bar.update(total=100, progress=100)
            self.phase("done, but --verify reported an error above 40 ms: check the log", ORANGE)
            self.notify("The result may be out of sync.", title="remuxy", severity="warning")
        elif rc < 0 or rc in (130, 143) or self.cancelled:
            bar.update(total=100, progress=0)
            self.phase("cancelled", RED)
        else:
            bar.update(total=100, progress=0)
            self.phase(f"failed (code {rc}): see the log", RED)
            self.notify("The remux failed; see the log.", title="remuxy", severity="error")
        eta.update("")
        self.cancelled = False

    def track_phase(self, line: str) -> None:
        """Updates the phase label (and the total duration for the progress bar) from remux's output."""
        m = re.search(r"ends at ([\d.]+)s", line)
        if m:
            self.total = float(m[1])
        if "decoding audio" in line or "measuring the exact duration" in line:
            self.phase("decoding the audio to measure it…", LILAC)
        elif line.startswith("[auto-sync]"):
            self.phase("auto-sync: measuring the delay…", LILAC)
        elif "Post-mux verification" in line:
            self.phase("verifying the sync of the result…", LILAC)

    def action_cancel(self) -> None:
        if not self.proc:
            return
        self.cancelled = True
        self.phase("cancelling…", RED)
        try:
            # remux handles SIGTERM: stops ffmpeg and deletes the partial file
            os.killpg(self.proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    async def action_quit(self) -> None:
        self.action_cancel()
        if self.proc:
            try:
                await asyncio.wait_for(self.proc.wait(), 10)
            except asyncio.TimeoutError:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.exit()
