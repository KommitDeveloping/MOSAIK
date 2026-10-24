"""Choosing files and folders.

Order of preference:
  * Windows / macOS: the operating system's own dialogs (through tkinter);
  * Linux: the desktop's dialog (zenity on GTK, kdialog on KDE) when installed;
  * otherwise (or with MOSAIK_FILE_DIALOG=builtin): Mosaik's own themed file browser.

Set MOSAIK_FILE_DIALOG to "builtin" or "system" to force one of them.
"""

from __future__ import annotations

import os
import shutil
import string
import subprocess
import sys
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from ..config import PHOTO_EXT, VIDEO_EXT
from ..utils import format_size, is_supported
from . import theme

FILTER_MEDIA = "Photos and videos"
FILTER_ALL = "All files"
MAX_ENTRIES = 5000

_last_dir = None  # remembered between dialogs


def _remember(path) -> None:
    global _last_dir
    p = Path(path)
    _last_dir = p if p.is_dir() else p.parent


# ---------------------------------------------------------------------------
# System dialogs
# ---------------------------------------------------------------------------

def _patterns() -> str:
    out = []
    for ext in sorted(PHOTO_EXT | VIDEO_EXT):
        out += [f"*{ext}", f"*{ext.upper()}"]
    return " ".join(out)


def _linux_command(kind: str, title: str):
    kde = "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    start = str(_last_dir or Path.home()) + "/"
    for tool in (("kdialog", "zenity") if kde else ("zenity", "kdialog")):
        exe = shutil.which(tool)
        if not exe:
            continue
        if tool == "zenity":
            cmd = [exe, "--file-selection", "--title", title, "--filename", start]
            if kind == "files":
                cmd += ["--multiple", "--separator=\n", f"--file-filter={FILTER_MEDIA} | {_patterns()}",
                        f"--file-filter={FILTER_ALL} | *"]
            else:
                cmd.append("--directory")
        else:
            cmd = [exe, "--title", title]
            if kind == "files":
                cmd += ["--multiple", "--separate-output", "--getopenfilename", start,
                        f"{_patterns()}|{FILTER_MEDIA}\n*|{FILTER_ALL}"]
            else:
                cmd += ["--getexistingdirectory", start]
        return cmd
    return None


def _system_pick(kind: str, title: str, root, force: bool):
    """Returns a list of paths (maybe empty if cancelled), or None if no system dialog exists."""
    if sys.platform.startswith("linux"):
        cmd = _linux_command(kind, title)
        if cmd is None:
            return None if not force else _tk_dialog(kind, title)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    text=True, encoding="utf-8", errors="replace")
            while proc.poll() is None:
                root.update()  # keep the window responsive while the dialog is open
                time.sleep(0.03)
            out = proc.stdout.read()
        except OSError:
            return None
        if proc.returncode == 0:
            return [line for line in out.splitlines() if line.strip()]
        if proc.returncode == 1:
            return []  # cancelled
        return None  # the tool crashed: fall back to the built-in browser
    return _tk_dialog(kind, title)  # native dialogs on Windows and macOS


def _tk_dialog(kind: str, title: str):
    start = str(_last_dir) if _last_dir else None
    if kind == "files":
        types = [(FILTER_MEDIA, " ".join(f"*{e}" for e in sorted(PHOTO_EXT | VIDEO_EXT))),
                 (FILTER_ALL, "*.*")]
        return list(filedialog.askopenfilenames(title=title, filetypes=types, initialdir=start))
    path = filedialog.askdirectory(title=title, initialdir=start)
    return [path] if path else []


# ---------------------------------------------------------------------------
# Built-in browser
# ---------------------------------------------------------------------------

def _places():
    home = Path.home()
    places = [("Home", home)]
    for label, name in (("Desktop", "Desktop"), ("Documents", "Documents"),
                        ("Downloads", "Downloads"), ("Pictures", "Pictures"),
                        ("Videos", "Videos"), ("Movies", "Movies")):
        if (home / name).is_dir():
            places.append((label, home / name))
    if sys.platform == "win32":
        for letter in string.ascii_uppercase:
            if os.path.isdir(f"{letter}:\\"):
                places.append((f"Drive {letter}:", Path(f"{letter}:\\")))
    else:
        places.append(("Computer", Path("/")))
        user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        for base in ("/Volumes", f"/media/{user}", f"/run/media/{user}", "/mnt"):
            try:
                for entry in sorted(Path(base).iterdir()):
                    if entry.is_dir() and not entry.name.startswith("."):
                        places.append((entry.name, entry))
            except OSError:
                continue
    return places


class FileBrowser(tk.Toplevel):
    """Themed, modal file browser. After it closes, `result` holds the chosen paths."""

    def __init__(self, parent, title: str, mode: str = "files", start=None, modal: bool = True):
        super().__init__(parent, bg=theme.BG)
        self.title(title)
        self.transient(parent)
        self.mode = mode
        self.result: list = []
        self.show_hidden = tk.BooleanVar(value=False)
        self.kind_filter = tk.StringVar(value=FILTER_MEDIA)
        self.path_var = tk.StringVar()
        self.status = tk.StringVar()
        self._kinds: dict = {}
        self._places = _places()

        self._build()
        folder = Path(start) if start else (_last_dir or Path.home())
        self.cwd = folder if folder.is_dir() else Path.home()
        self._go(self.cwd)

        self.update_idletasks()
        width, height = 880, 560
        x = max(0, parent.winfo_rootx() + (parent.winfo_width() - width) // 2)
        y = max(0, parent.winfo_rooty() + (parent.winfo_height() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(700, 440)
        self.bind("<Escape>", lambda _e: self.destroy())
        if not modal:  # used by the tests: the caller drives the window
            return
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()
        self.wait_window(self)

    # ----- layout -----

    def _build(self):
        top = ttk.Frame(self, padding=(14, 12, 14, 8))
        top.pack(fill="x")
        ttk.Button(top, text="Up", width=5, command=self.go_up).pack(side="left")
        ttk.Button(top, text="Home", width=6,
                   command=lambda: self._go(Path.home())).pack(side="left", padx=(6, 0))
        entry = ttk.Entry(top, textvariable=self.path_var)
        entry.pack(side="left", fill="x", expand=True, padx=10)
        entry.bind("<Return>", self._on_path_entered)
        ttk.Checkbutton(top, text="Hidden files", variable=self.show_hidden,
                        command=self._refresh, style="Bg.TCheckbutton").pack(side="left")

        body = ttk.Frame(self, padding=(14, 0, 14, 0))
        body.pack(fill="both", expand=True)
        self.sidebar = theme.styled_listbox(body, width=18, height=10)
        self.sidebar.pack(side="left", fill="y")
        for label, _ in self._places:
            self.sidebar.insert("end", "  " + label)
        self.sidebar.bind("<<ListboxSelect>>", self._on_place)

        frame = ttk.Frame(body)
        frame.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.tree = ttk.Treeview(frame, columns=("size", "modified"),
                                 selectmode="extended" if self.mode == "files" else "browse")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("modified", text="Modified", anchor="w")
        self.tree.column("#0", width=380, stretch=True)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("modified", width=140, stretch=False)
        self.tree.tag_configure("dir", foreground="#ff8a8e")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Return>", lambda _e: self._accept())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())

        bottom = ttk.Frame(self, padding=(14, 10, 14, 14))
        bottom.pack(fill="x")
        if self.mode == "files":
            box = ttk.Combobox(bottom, textvariable=self.kind_filter, state="readonly", width=20,
                               values=[FILTER_MEDIA, FILTER_ALL])
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda _e: self._refresh())
        ttk.Label(bottom, textvariable=self.status, style="Muted.TLabel").pack(side="left", padx=12)
        self.ok_btn = ttk.Button(bottom, style="Accent.TButton", command=self._accept)
        self.ok_btn.pack(side="right")
        ttk.Button(bottom, text="Cancel", command=self.destroy).pack(side="right", padx=(0, 8))
        self._on_select()

    # ----- navigation -----

    def go_up(self):
        parent = self.cwd.parent
        if parent != self.cwd:
            self._go(parent)

    def _on_path_entered(self, _event=None):
        target = Path(os.path.expanduser(self.path_var.get().strip()))
        if target.is_dir():
            self._go(target)
        else:
            self.status.set("That folder does not exist.")

    def _on_place(self, _event=None):
        selection = self.sidebar.curselection()
        if selection:
            self._go(self._places[selection[0]][1])
            self.sidebar.selection_clear(0, "end")

    def _refresh(self):
        self._go(self.cwd)

    def _go(self, folder: Path):
        try:
            entries = list(os.scandir(folder))
        except OSError as exc:
            self.status.set(f"Cannot open this folder: {exc.strerror or exc}")
            return
        self.cwd = Path(folder)
        self.path_var.set(str(self.cwd))
        self.tree.delete(*self.tree.get_children())
        self._kinds.clear()

        hidden = self.show_hidden.get()
        only_media = self.mode == "files" and self.kind_filter.get() == FILTER_MEDIA
        dirs, files = [], []
        for entry in entries:
            if not hidden and entry.name.startswith("."):
                continue
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                dirs.append(entry)
            elif self.mode == "files" and (not only_media or is_supported(entry.name)):
                files.append(entry)
        key = lambda e: e.name.lower()  # noqa: E731
        for entry in (sorted(dirs, key=key) + sorted(files, key=key))[:MAX_ENTRIES]:
            try:
                st = entry.stat()
                modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                size = "" if entry.is_dir() else format_size(st.st_size)
            except OSError:
                modified = size = ""
            kind = "dir" if entry.is_dir() else "file"
            self._kinds[entry.path] = kind
            self.tree.insert("", "end", iid=entry.path, values=(size, modified),
                             text=entry.name + ("/" if kind == "dir" else ""),
                             tags=("dir",) if kind == "dir" else ())
        self.tree.yview_moveto(0)
        self._on_select()

    # ----- selection -----

    def _on_select(self):
        selected = self.tree.selection()
        if self.mode == "files":
            files = [s for s in selected if self._kinds.get(s) == "file"]
            self.ok_btn.configure(text=f"Add {len(files)} file(s)" if files else "Add",
                                  state="normal" if files else "disabled")
            self.status.set(f"{len(files)} selected" if files else f"{len(self._kinds)} items")
        else:
            chosen = [s for s in selected if self._kinds.get(s) == "dir"]
            self.ok_btn.configure(text="Use selected folder" if chosen else "Use this folder",
                                  state="normal")
            self.status.set(f"{len(self._kinds)} items")

    def _on_double(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if self._kinds.get(row) == "dir":
            self._go(Path(row))
        elif self.mode == "files":
            self.result = [row]
            _remember(row)
            self.destroy()

    def _accept(self):
        selected = self.tree.selection()
        if self.mode == "files":
            files = [s for s in selected if self._kinds.get(s) == "file"]
            if not files:
                return
            self.result = files
        else:
            dirs = [s for s in selected if self._kinds.get(s) == "dir"]
            self.result = [dirs[0] if dirs else str(self.cwd)]
        _remember(self.result[0])
        self.destroy()


def _builtin_pick(kind: str, title: str, root) -> list:
    return FileBrowser(root, title, "files" if kind == "files" else "dir").result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _pick(kind: str, title: str, root) -> list:
    choice = os.environ.get("MOSAIK_FILE_DIALOG", "auto").strip().lower()
    if choice != "builtin":
        result = _system_pick(kind, title, root, force=(choice == "system"))
        if result is not None:
            if result:
                _remember(result[0])
            return result
    return _builtin_pick(kind, title, root)


def pick_files(root, title: str = "Choose photos and videos") -> list:
    """Ask for one or more files. Returns [] if cancelled."""
    return _pick("files", title, root)


def pick_folder(root, title: str = "Choose a folder") -> list:
    """Ask for a folder. Returns [] if cancelled, otherwise a one-item list."""
    return _pick("dir", title, root)
