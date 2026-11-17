"""File picker dialog: a folder tree that only lists media files (or, for the output, lets you type a name)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Input, Label

MEDIA_EXT = {".mkv", ".mka", ".mk3d", ".mp4", ".m4v", ".m4a", ".mov", ".avi", ".vob", ".mpg", ".mpeg",
             ".m2ts", ".ts", ".webm", ".mp3", ".mp2", ".aac", ".ac3", ".eac3", ".ec3", ".dts", ".thd",
             ".mlp", ".flac", ".wav", ".opus", ".ogg", ".wma", ".wmv"}


class MediaTree(DirectoryTree):
    """Directory tree that hides dotfiles and shows only folders and media files."""

    def filter_paths(self, paths):
        return [p for p in paths if not p.name.startswith(".")
                and (p.is_dir() or p.suffix.lower() in MEDIA_EXT)]


class PickFile(ModalScreen[Optional[str]]):
    """Dialog to choose a file (or, for the output, type the path). Dismisses with the path or None."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel"),
                Binding("backspace", "up", "Parent folder", show=True)]

    def __init__(self, title: str, start: Path, save: bool = False) -> None:
        super().__init__()
        self.title_text, self.start, self.save = title, start.expanduser().resolve(), save

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Label(self.title_text, id="picker-title")
            yield Label(str(self.start), id="picker-dir")
            yield MediaTree(self.start, id="tree")
            if self.save:
                yield Input(placeholder="output file name (.mkv), then Enter", id="picker-name")
            yield Label("Enter opens/chooses · Backspace goes up a folder · Esc cancels", id="picker-help")

    def on_mount(self) -> None:
        self.query_one(MediaTree).focus()

    def action_up(self) -> None:
        if isinstance(self.focused, Input):
            return
        tree = self.query_one(MediaTree)
        parent = Path(tree.path).resolve().parent
        tree.path = parent
        self.query_one("#picker-dir", Label).update(str(parent))

    @on(DirectoryTree.FileSelected)
    def chosen(self, ev: DirectoryTree.FileSelected) -> None:
        if self.save:
            self.query_one("#picker-name", Input).value = str(ev.path)
            self.query_one("#picker-name", Input).focus()
        else:
            self.dismiss(str(ev.path))

    @on(DirectoryTree.DirectorySelected)
    def dir_chosen(self, ev: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#picker-dir", Label).update(str(ev.path))
        if self.save:
            box = self.query_one("#picker-name", Input)
            name = Path(box.value).name if box.value else ""
            box.value = str(Path(ev.path) / name) if name else str(ev.path) + os.sep

    @on(Input.Submitted, "#picker-name")
    def name_done(self, ev: Input.Submitted) -> None:
        v = ev.value.strip()
        if v:
            p = Path(v).expanduser()
            if not p.is_absolute():
                p = Path(self.query_one("#picker-dir", Label).content.__str__()) / p
            self.dismiss(str(p if p.suffix else p.with_suffix(".mkv")))
