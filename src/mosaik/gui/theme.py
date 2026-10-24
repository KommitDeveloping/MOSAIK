"""Red and black theme, window sizing and the logo."""

from __future__ import annotations

import random
import sys
import tkinter as tk
from tkinter import ttk

BG = "#0e0e0f"
PANEL = "#181819"
FIELD = "#262627"
ACCENT = "#d71920"
ACCENT_HOVER = "#f0343a"
ACCENT_DISABLED = "#5c1519"
FG = "#f3f1ef"
MUTED = "#a3a09d"
LINE = "#3a3a3c"
WIDTH = 760


def enable_dpi_awareness() -> None:
    """Crisp text on high-DPI Windows screens (no effect elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass


def setup_style(root: tk.Misc) -> None:
    root.configure(bg=BG)
    style = ttk.Style()
    try:
        style.theme_use("clam")  # the only built-in theme that honours custom colours everywhere
    except tk.TclError:
        pass
    style.configure(".", background=BG, foreground=FG, font=("TkDefaultFont", 10))
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Card.TLabel", background=PANEL, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("TkDefaultFont", 9))
    style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED, font=("TkDefaultFont", 9))
    style.configure("Title.TLabel", background=BG, foreground=FG, font=("TkDefaultFont", 22, "bold"))
    style.configure("Step.TLabel", background=PANEL, foreground=ACCENT, font=("TkDefaultFont", 10, "bold"))
    style.configure("Status.TLabel", background=BG, foreground=FG, font=("TkDefaultFont", 10))
    style.configure("TButton", background=FIELD, foreground=FG, padding=(10, 5), borderwidth=0)
    style.map("TButton", background=[("active", "#38383a"), ("disabled", PANEL)],
              foreground=[("disabled", "#6c6a68")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    padding=(14, 9), font=("TkDefaultFont", 11, "bold"))
    style.map("Accent.TButton",
              background=[("active", ACCENT_HOVER), ("disabled", ACCENT_DISABLED)],
              foreground=[("disabled", "#c9a9ab")])
    for name in ("TRadiobutton", "TCheckbutton"):
        style.configure(name, background=PANEL, foreground=FG)
        style.map(name, background=[("active", PANEL)], foreground=[("disabled", MUTED)])
    style.configure("Bg.TCheckbutton", background=BG, foreground=MUTED)
    style.map("Bg.TCheckbutton", background=[("active", BG)])
    style.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=FG,
                    arrowcolor=FG, bordercolor=LINE, lightcolor=FIELD, darkcolor=FIELD)
    style.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)])
    style.configure("TEntry", fieldbackground=FIELD, foreground=FG, bordercolor=LINE,
                    lightcolor=FIELD, darkcolor=FIELD, insertcolor=FG)
    style.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT,
                    bordercolor=PANEL, lightcolor=ACCENT, darkcolor=ACCENT)
    style.configure("TScrollbar", background=FIELD, troughcolor=PANEL, bordercolor=PANEL,
                    arrowcolor=FG)
    style.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG,
                    bordercolor=LINE, lightcolor=FIELD, darkcolor=FIELD, rowheight=26, borderwidth=0)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=PANEL, foreground=MUTED, relief="flat",
                    padding=(6, 4), font=("TkDefaultFont", 9, "bold"))
    style.map("Treeview.Heading", background=[("active", PANEL)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")


def fix_window(root: tk.Tk, min_width: int = WIDTH) -> None:
    """Fixed size computed from the real content: everything fits on any system and font."""
    root.update_idletasks()
    width = max(root.winfo_reqwidth(), min_width)
    height = root.winfo_reqheight()
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 3)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.resizable(False, False)


def logo(parent) -> tk.Canvas:
    """All-red mosaic, shading from bright red (top left) to dark red (bottom right)."""
    rnd = random.Random(5)
    light, dark = (255, 74, 79), (92, 8, 14)
    size, cell = 6, 8
    canvas = tk.Canvas(parent, width=size * cell, height=size * cell, bg=BG, highlightthickness=0)
    for row in range(size):
        for col in range(size):
            t = (row + col) / (2 * (size - 1)) + rnd.uniform(-0.09, 0.09)
            t = min(1.0, max(0.0, t))
            r, g, b = (round(lo + (hi - lo) * t) for lo, hi in zip(light, dark))
            color = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_rectangle(col * cell, row * cell, col * cell + cell - 1,
                                    row * cell + cell - 1, fill=color, outline="")
    return canvas


def styled_listbox(parent, **kwargs) -> tk.Listbox:
    options = dict(
        bg=FIELD, fg=FG, relief="flat", highlightthickness=1, highlightbackground=LINE,
        highlightcolor=ACCENT, selectbackground=ACCENT, selectforeground="#ffffff",
        activestyle="none", exportselection=False, borderwidth=0,
    )
    options.update(kwargs)
    return tk.Listbox(parent, **options)
