"""Mosaik main window."""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import __version__, bootstrap
from ..config import Settings, SetupError
from ..utils import format_size, is_supported, is_video, open_folder, output_path
from . import theme
from .filepicker import pick_files, pick_folder

try:  # optional: drag & drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # noqa: BLE001 - missing package or unsupported platform
    DND_FILES = TkinterDnD = None

QUALITY_LABELS = {
    "Fast": "fast",
    "Balanced (recommended)": "balanced",
    "Maximum precision (slower)": "max",
}
STRENGTH_LABELS = {"Light": "light", "Medium": "medium", "Strong": "strong"}
AUDIO_LABELS = {
    "Remove audio (safest)": "mute",
    "Distort voice": "anon",
    "Keep original audio": "keep",
}
MAX_FOLDER_FILES = 500


def create_root():
    """A Tk root, with drag & drop support when available."""
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk()
        except Exception:  # noqa: BLE001 - e.g. the tkdnd library cannot load
            pass
    return tk.Tk()


class _Queued:
    """Run callables on the Tk thread: worker threads never touch widgets directly."""

    def _init_queue(self):
        self.events: queue.Queue = queue.Queue()

    def post(self, fn):
        self.events.put(fn)

    def _drain(self):
        try:
            while True:
                self.events.get_nowait()()
        except queue.Empty:
            pass
        try:
            self.root.after(100, self._drain)
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# First run: automatic installation
# ---------------------------------------------------------------------------

class SetupScreen(_Queued):
    def __init__(self, root: tk.Tk, files=()):
        self.root = root
        self.files = list(files)
        self._init_queue()
        root.title("Mosaik - first run")
        theme.setup_style(root)

        frame = ttk.Frame(root, padding=22)
        frame.pack(fill="both", expand=True)
        head = ttk.Frame(frame)
        head.pack(fill="x")
        theme.logo(head).pack(side="left", padx=(0, 14))
        ttk.Label(head, text="Mosaik", style="Title.TLabel").pack(side="left")
        ttk.Label(
            frame, wraplength=500,
            text="First run: setting up everything Mosaik needs.\n"
                 "This needs internet and a few minutes, and only happens once.",
        ).pack(anchor="w", pady=(16, 10))
        self.bar = ttk.Progressbar(frame, mode="indeterminate")
        self.bar.pack(fill="x")
        self.bar.start(12)
        self.status = ttk.Label(frame, text="Preparing...", style="Muted.TLabel")
        self.status.pack(anchor="w", pady=(6, 8))
        self.text = tk.Text(frame, height=9, width=64, bg=theme.PANEL, fg=theme.MUTED, relief="flat",
                            state="disabled", wrap="word", font="TkFixedFont", highlightthickness=0)
        self.text.pack(fill="x")
        theme.fix_window(root, 560)

        root.after(100, self._drain)
        threading.Thread(target=self._work, daemon=True).start()

    def _log(self, message):
        def add():
            self.text.configure(state="normal")
            self.text.insert("end", str(message)[:300] + "\n")
            self.text.see("end")
            self.text.configure(state="disabled")
            self.status.configure(text=str(message)[:80])
        self.post(add)

    def _work(self):
        try:
            python = bootstrap.install_environment(self._log)
        except SetupError as exc:
            self.post(lambda message=str(exc): self._fail(message))
            return
        except Exception as exc:  # noqa: BLE001
            self.post(lambda message=f"Unexpected error: {exc}": self._fail(message))
            return
        self.post(lambda: self._done(python))

    def _done(self, python):
        args = ["--gui", *self.files] if self.files else []
        self.root.destroy()
        bootstrap.relaunch(python, args)  # replaces this process on POSIX

    def _fail(self, message):
        self.bar.stop()
        messagebox.showerror("Setup failed", message)
        self.root.destroy()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class MosaikApp(_Queued):
    def __init__(self, root: tk.Tk, files=()):
        self.root = root
        root.title(f"Mosaik {__version__}")
        theme.setup_style(root)
        self._init_queue()

        self.files: list = []
        self.dest_mode = tk.StringVar(value="same")
        self.dest_dir = tk.StringVar()
        self.quality = tk.StringVar(value="Balanced (recommended)")
        self.strength = tk.StringVar(value="Medium")
        self.audio = tk.StringVar(value="Remove audio (safest)")
        self.strip = tk.BooleanVar(value=True)
        self.progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="Add a few photos or videos to get started.")
        self.last_folder = None
        self.cancel_flag = threading.Event()
        self.busy = False
        self._picking = False
        self.dnd_enabled = False
        self._log_lines: list = []
        self._log_win = None
        self._log_text = None

        self._build()
        if files:
            self.add_paths(files)
        else:
            self._refresh_list()
        theme.fix_window(root)
        root.after(100, self._drain)

    # ----- layout -----

    def _card(self, parent, step, title):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
        card.pack(fill="x", pady=(0, 8))
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text=step, style="Step.TLabel").pack(side="left")
        ttk.Label(header, text="  " + title, style="Card.TLabel",
                  font=("TkDefaultFont", 10, "bold")).pack(side="left")
        return card

    def _build(self):
        outer = ttk.Frame(self.root, padding=(20, 12, 20, 10))
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x", pady=(0, 10))
        theme.logo(head).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text="Mosaik", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, style="Muted.TLabel",
                  text="Censor faces with a mosaic, in photos and videos. Everything stays on your computer.",
                  ).pack(anchor="w")

        # 1 - files
        card = self._card(outer, "1", "Choose photos and videos")
        self.zone = tk.Canvas(card, height=50, bg=theme.FIELD, highlightthickness=0, cursor="hand2")
        self.zone.pack(fill="x", pady=(0, 6))
        self.zone.bind("<Configure>", self._draw_zone)
        self.zone.bind("<Button-1>", lambda _e: self.add_files())
        self.zone.bind("<Enter>", lambda _e: self._draw_zone(hover=True))
        self.zone.bind("<Leave>", lambda _e: self._draw_zone(hover=False))
        self._enable_drop(self.zone)

        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill="x")
        list_frame = ttk.Frame(body, style="Card.TFrame")
        list_frame.pack(side="left", fill="x", expand=True)
        self.listbox = theme.styled_listbox(list_frame, height=3, selectmode="extended")
        self.listbox.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        sb.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)
        self._enable_drop(self.listbox)
        buttons = ttk.Frame(body, style="Card.TFrame")
        buttons.pack(side="left", padx=(10, 0), anchor="n")
        self.add_btn = ttk.Button(buttons, text="Add files...", command=self.add_files, width=12)
        self.add_btn.pack(pady=(0, 3))
        self.folder_btn = ttk.Button(buttons, text="Add folder...", command=self.add_folder, width=12)
        self.folder_btn.pack(pady=(0, 3))
        self.rem_btn = ttk.Button(buttons, text="Remove", command=self.remove_selected, width=12)
        self.rem_btn.pack(pady=(0, 3))
        self.clr_btn = ttk.Button(buttons, text="Clear", command=self.clear_files, width=12)
        self.clr_btn.pack()

        # 2 - destination
        card = self._card(outer, "2", "Where to save the results")
        ttk.Radiobutton(card, text="Next to the originals (name_mosaik.jpg / .mp4)",
                        variable=self.dest_mode, value="same", command=self._sync_dest).pack(anchor="w")
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", pady=(4, 0))
        ttk.Radiobutton(row, text="In a folder:", variable=self.dest_mode, value="dir",
                        command=self._sync_dest).pack(side="left")
        self.dest_entry = ttk.Entry(row, textvariable=self.dest_dir, state="disabled")
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.dest_btn = ttk.Button(row, text="Choose...", command=self.choose_dest, state="disabled")
        self.dest_btn.pack(side="left")
        ttk.Label(card, style="CardMuted.TLabel",
                  text="Originals are never modified or overwritten.").pack(anchor="w", pady=(6, 0))

        # 3 - options
        card = self._card(outer, "3", "Options")
        grid = ttk.Frame(card, style="Card.TFrame")
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        def option(row_, label, var, values, hint):
            ttk.Label(grid, text=label, style="Card.TLabel").grid(row=row_, column=0, sticky="w", pady=3)
            box = ttk.Combobox(grid, textvariable=var, values=list(values), state="readonly", width=32)
            box.grid(row=row_, column=1, sticky="w", padx=10, pady=3)
            ttk.Label(grid, text=hint, style="CardMuted.TLabel").grid(row=row_, column=2, sticky="w")
            return box

        self.opt_boxes = [
            option(0, "Precision", self.quality, QUALITY_LABELS, "higher = finds more faces"),
            option(1, "Mosaic strength", self.strength, STRENGTH_LABELS, "strong = bigger blocks"),
            option(2, "Video audio", self.audio, AUDIO_LABELS, "videos only"),
        ]
        self.strip_check = ttk.Checkbutton(
            card, text="Remove metadata (GPS location, date, camera model...)", variable=self.strip)
        self.strip_check.pack(anchor="w", pady=(6, 0))

        # run
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(2, 8))
        actions.columnconfigure(0, weight=1)
        self.start_btn = ttk.Button(actions, text="Start censoring", style="Accent.TButton",
                                    command=self.start)
        self.start_btn.grid(row=0, column=0, sticky="ew")
        self.cancel_btn = ttk.Button(actions, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=(8, 0))
        self.open_btn = ttk.Button(actions, text="Open folder", command=self.open_results,
                                   state="disabled")
        self.open_btn.grid(row=0, column=2, padx=(8, 0))
        ttk.Button(actions, text="Log", command=self.show_log, width=5).grid(
            row=0, column=3, padx=(8, 0))

        ttk.Progressbar(outer, variable=self.progress, maximum=100).pack(fill="x", pady=(0, 4))
        ttk.Label(outer, textvariable=self.status, style="Status.TLabel", width=88).pack(anchor="w")

        ttk.Label(
            outer, style="Muted.TLabel", wraplength=theme.WIDTH - 60, justify="left",
            text="Always check the result: no detector finds every face (very small, covered or "
                 "blurry ones can slip through) and a distorted voice does not guarantee anonymity.",
        ).pack(anchor="w")

    # ----- drop zone -----

    def _enable_drop(self, widget):
        if DND_FILES is None:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_enabled = True
        except Exception:  # noqa: BLE001
            pass

    def _on_drop(self, event):
        self.add_paths(self.root.tk.splitlist(event.data))
        return event.action

    def _draw_zone(self, event=None, hover=False):
        zone = self.zone
        zone.delete("all")
        width, height = zone.winfo_width(), zone.winfo_height()
        color = theme.ACCENT_HOVER if hover else theme.ACCENT
        zone.create_rectangle(4, 4, width - 5, height - 5, outline=color, dash=(5, 4), width=2)
        line1 = "Drop photos and videos here" if self.dnd_enabled else "Click to choose photos and videos"
        zone.create_text(width / 2, height / 2 - 8, text=line1, fill=theme.FG,
                         font=("TkDefaultFont", 11, "bold"))
        zone.create_text(width / 2, height / 2 + 10, fill=theme.MUTED, font=("TkDefaultFont", 9),
                         text="or click here to browse" if self.dnd_enabled
                         else "JPG, PNG, WebP, MP4, MOV, MKV and more")

    # ----- files -----

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        if not self.files:
            self.listbox.insert("end", "  No files yet")
            self.listbox.itemconfig(0, fg=theme.MUTED, selectforeground=theme.MUTED,
                                    selectbackground=theme.FIELD)
            return
        for path in self.files:
            tag = "VIDEO" if is_video(path) else "PHOTO"
            try:
                size = format_size(Path(path).stat().st_size)
            except OSError:
                size = "?"
            self.listbox.insert("end", f" [{tag}]  {Path(path).name}   ({size})")

    def add_paths(self, paths):
        """Add files and (recursively) the supported files inside folders."""
        found, skipped = [], 0
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                count = 0
                for root_dir, _dirs, names in os.walk(p):
                    for name in sorted(names):
                        if is_supported(name) and count < MAX_FOLDER_FILES:
                            found.append(str(Path(root_dir) / name))
                            count += 1
            elif p.is_file() and is_supported(p):
                found.append(str(p))
            else:
                skipped += 1
        known = {os.path.realpath(f) for f in self.files}
        added = 0
        for path in found:
            real = os.path.realpath(path)
            if real not in known:
                known.add(real)
                self.files.append(path)
                added += 1
        self._refresh_list()
        if added or skipped:
            note = f"  ({skipped} unsupported skipped)" if skipped else ""
            self.status.set(f"{len(self.files)} file(s) ready. Press 'Start censoring'.{note}")

    def _pick(self, picker, title):
        if self._picking or self.busy:
            return []
        self._picking = True
        try:
            return picker(self.root, title)
        finally:
            self._picking = False

    def add_files(self):
        self.add_paths(self._pick(pick_files, "Choose photos and videos"))

    def add_folder(self):
        self.add_paths(self._pick(pick_folder, "Choose a folder with photos and videos"))

    def remove_selected(self):
        for index in reversed(self.listbox.curselection()):
            if index < len(self.files):
                del self.files[index]
        self._refresh_list()

    def clear_files(self):
        self.files.clear()
        self._refresh_list()

    def _sync_dest(self):
        state = "normal" if self.dest_mode.get() == "dir" else "disabled"
        self.dest_entry.configure(state=state)
        self.dest_btn.configure(state=state)

    def choose_dest(self):
        paths = self._pick(pick_folder, "Choose the destination folder")
        if paths:
            self.dest_dir.set(paths[0])

    # ----- running -----

    def _set_busy(self, busy: bool):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in (self.start_btn, self.add_btn, self.folder_btn, self.rem_btn, self.clr_btn,
                       self.strip_check):
            widget.configure(state=state)
        for box in self.opt_boxes:
            box.configure(state="disabled" if busy else "readonly")
        self.cancel_btn.configure(state="normal" if busy else "disabled")

    def start(self):
        if not self.files:
            messagebox.showinfo("No files", "Add at least one photo or video.")
            return
        out_dir = None
        if self.dest_mode.get() == "dir":
            out_dir = self.dest_dir.get().strip()
            if not out_dir or not Path(out_dir).is_dir():
                messagebox.showerror("Folder missing", "Choose a valid destination folder.")
                return
        settings = Settings(
            quality=QUALITY_LABELS[self.quality.get()],
            strength=STRENGTH_LABELS[self.strength.get()],
            audio=AUDIO_LABELS[self.audio.get()],
            strip_metadata=self.strip.get(),
        )
        self.cancel_flag.clear()
        self._set_busy(True)
        self.open_btn.configure(state="disabled")
        self.progress.set(0)
        self.status.set("Starting...")
        threading.Thread(target=self._worker, args=(list(self.files), settings, out_dir),
                         daemon=True).start()

    def cancel(self):
        self.cancel_flag.set()
        self.cancel_btn.configure(state="disabled")
        self.status.set("Cancelling...")

    def _worker(self, files, settings, out_dir):
        done = failed = faces = 0
        outputs = []
        try:
            from ..config import CancelledError
            from ..detect import FaceFinder
            from ..models import ensure_model
            from ..pipeline import process_file

            finder = FaceFinder(ensure_model(None, self.log), settings.quality)
            for i, source in enumerate(files):
                if self.cancel_flag.is_set():
                    break
                name = Path(source).name
                self.log(f"[{i + 1}/{len(files)}] {name}")

                def progress(fraction, text, i=i, name=name):
                    self.ui((i + fraction) / len(files) * 100,
                            f"{i + 1}/{len(files)} - {name} - {text}")

                try:
                    target = output_path(source, out_dir)
                    result = process_file(source, target, settings, finder, log=self.log,
                                          progress=progress, cancelled=self.cancel_flag.is_set)
                except CancelledError:
                    self.log("  cancelled")
                    break
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    self.log(f"  ERROR: {exc}")
                    continue
                done += 1
                faces += result.faces
                outputs.append(result.path)
                self.log(f"  saved: {result.path}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR: {exc}")
            self.post(lambda m=str(exc): messagebox.showerror("Error", m))
            failed += 1
        finally:
            self.post(lambda: self._finished(done, failed, faces, outputs))

    def _finished(self, done, failed, faces, outputs):
        self._set_busy(False)
        if outputs:
            self.last_folder = str(Path(outputs[-1]).parent)
            self.open_btn.configure(state="normal")
        if self.cancel_flag.is_set():
            self.status.set(f"Cancelled. Files completed: {done}.")
            return
        self.progress.set(100 if done else 0)
        note = " Press 'Log' for details." if failed else ""
        self.status.set(f"Finished: {done} processed, {failed} failed. Faces censored: {faces}.{note}")
        if done:
            messagebox.showinfo(
                "Mosaik",
                f"Done! {done} file(s) processed" + (f", {failed} failed" if failed else "")
                + f".\nFaces censored: {faces}.\n\nPlease check the result: the detector can miss "
                  "very small, covered or blurry faces.")

    def open_results(self):
        if self.last_folder:
            open_folder(self.last_folder)

    # ----- thread-safe UI helpers -----

    def ui(self, progress=None, status=None):
        def apply():
            if progress is not None:
                self.progress.set(progress)
            if status is not None:
                self.status.set(status)
        self.post(apply)

    def log(self, message):
        def add():
            line = str(message).rstrip()
            self._log_lines.append(line)
            del self._log_lines[:-2000]
            if self._log_text is not None and self._log_win.winfo_exists():
                self._append_log(line)
        self.post(add)

    def _append_log(self, line):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def show_log(self):
        """Processing details live in their own small window, keeping the main one compact."""
        if self._log_win is not None and self._log_win.winfo_exists():
            self._log_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("Mosaik - log")
        win.configure(bg=theme.PANEL)
        win.geometry("700x320")
        text = tk.Text(win, wrap="word", state="disabled", bg=theme.PANEL, fg=theme.MUTED,
                       relief="flat", highlightthickness=0, font="TkFixedFont")
        bar = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self._log_win, self._log_text = win, text
        for line in self._log_lines:
            self._append_log(line)


# ---------------------------------------------------------------------------

def main(files=None) -> int:
    files = list(files or [])
    state = bootstrap.setup_state()
    relaunched = bool(os.environ.get(bootstrap.ENV_RELAUNCHED))

    if state == "required" and not relaunched:
        python = bootstrap.find_ready_python()
        if python:  # already installed in Mosaik's private environment: just switch to it
            bootstrap.relaunch(python, ["--gui", *files] if files else [])
            return 0

    theme.enable_dpi_awareness()
    root = create_root()
    if state == "required" and relaunched:
        root.withdraw()
        messagebox.showerror(
            "Mosaik",
            "The libraries are installed but cannot be loaded.\n"
            f"Try deleting the folder {bootstrap._venv_dir()} and starting Mosaik again.")
        return 1
    if state in ("required", "optional"):
        SetupScreen(root, files)
    else:
        MosaikApp(root, files)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
