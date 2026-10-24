"""Small helpers shared by every module. Standard library only."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import PHOTO_EXT, VIDEO_EXT


def data_dir() -> Path:
    """Per-user folder for Mosaik's private environment and cached files."""
    override = os.environ.get("MOSAIK_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Mosaik"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Mosaik"
    else:  # Linux, BSD and anything else POSIX-like
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "mosaik"
    base.mkdir(parents=True, exist_ok=True)
    return base


def hidden_flags() -> dict:
    """subprocess options that stop console windows from flashing on Windows."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def is_video(path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXT


def is_photo(path) -> bool:
    return Path(path).suffix.lower() in PHOTO_EXT


def is_supported(path) -> bool:
    return is_photo(path) or is_video(path)


def output_path(source, out_dir=None) -> str:
    """Name of the result file: <name>_mosaik.<ext>, never overwriting an existing file."""
    src = Path(source)
    ext = ".mp4" if is_video(src) else src.suffix.lower()
    folder = Path(out_dir) if out_dir else src.parent
    candidate = folder / f"{src.stem}_mosaik{ext}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{src.stem}_mosaik ({n}){ext}"
        n += 1
    return str(candidate)


def format_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def open_folder(path) -> None:
    """Show a folder in the system file manager."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass
