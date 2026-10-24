"""Automatic first-run setup. Standard library only: it must work before anything is installed.

Strategy: if the needed libraries are missing, create a private virtual environment in the
user's data folder, install them there with pip, and relaunch Mosaik inside it. This works
on systems that forbid system-wide pip (Arch/Manjaro, recent Debian/Ubuntu/Mint, Homebrew...).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from .config import OPTIONAL_REQUIREMENTS, REQUIREMENTS, SetupError
from .utils import data_dir, hidden_flags

ENV_RELAUNCHED = "MOSAIK_RELAUNCHED"


def deps_ready() -> bool:
    """True when the libraries needed to process media can be imported."""
    try:
        import cv2
        import numpy  # noqa: F401
    except ImportError:
        return False
    return hasattr(cv2, "FaceDetectorYN")


def optional_ready() -> bool:
    return importlib.util.find_spec("tkinterdnd2") is not None


def _marker() -> Path:
    return data_dir() / "optional_attempted"


def setup_state() -> str:
    """'required' (must install), 'optional' (nice-to-have missing, try once) or 'ready'."""
    if not deps_ready():
        return "required"
    # Drag & drop is only attempted inside a virtual environment: pip refuses (PEP 668) or
    # pollutes a system-wide Python.
    if (_in_virtualenv() and not optional_ready() and not _marker().exists()
            and not os.environ.get(ENV_RELAUNCHED)):
        return "optional"
    return "ready"


def _in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _venv_dir() -> Path:
    return data_dir() / "venv"


def _venv_python() -> Path:
    sub = ("Scripts", "python.exe") if sys.platform == "win32" else ("bin", "python")
    return _venv_dir().joinpath(*sub)


def find_ready_python():
    """Mosaik's private environment, if it already has the libraries; otherwise None."""
    python = _venv_python()
    if not python.exists():
        return None
    try:
        code = subprocess.run(
            [str(python), "-c", "import cv2, numpy; cv2.FaceDetectorYN"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=60, **hidden_flags(),
        ).returncode
    except (OSError, subprocess.TimeoutExpired):
        return None
    return str(python) if code == 0 else None


def _run_logged(cmd, log) -> int:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", **hidden_flags(),
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    return proc.wait()


def _venv_hint() -> str:
    if sys.platform == "darwin":
        return "Install Python from https://www.python.org/downloads/ and try again."
    if sys.platform == "win32":
        return "Reinstall Python from https://www.python.org/downloads/ (keep 'pip' selected)."
    return (
        "Install the venv module for your distribution and try again:\n"
        "  Debian/Ubuntu/Mint: sudo apt install python3-venv python3-pip\n"
        "  Fedora: sudo dnf install python3-pip\n"
        "  Arch/Manjaro: sudo pacman -S python-pip\n"
        "  openSUSE: sudo zypper install python3-pip"
    )


def install_environment(log=print, optional: bool = True) -> str:
    """Install the dependencies and return the Python interpreter to run Mosaik with."""
    if _in_virtualenv():
        python = sys.executable
    else:
        python = str(_venv_python())
        if not Path(python).exists():
            log("Creating a private Python environment for Mosaik...")
            code = _run_logged([sys.executable, "-m", "venv", str(_venv_dir())], log)
            if code != 0 or not Path(python).exists():
                raise SetupError("Could not create the Python environment.\n" + _venv_hint())

    pip = [python, "-m", "pip", "install", "--disable-pip-version-check", "--default-timeout", "60"]
    log("Installing libraries (numpy, OpenCV, portable FFmpeg)...")
    if _run_logged(pip + REQUIREMENTS, log) != 0:
        raise SetupError(
            "Installing the libraries failed. Check your internet connection and start "
            "Mosaik again.\nOn an unusual platform you can install them manually: "
            "pip install " + " ".join(REQUIREMENTS)
        )
    if optional and OPTIONAL_REQUIREMENTS:
        log("Installing drag & drop support (optional)...")
        if _run_logged(pip + OPTIONAL_REQUIREMENTS, log) != 0:
            log("Drag & drop support could not be installed; continuing without it.")
    try:
        _marker().write_text("1")
    except OSError:
        pass
    return python


def relaunch(python: str, args=(), wait: bool = False) -> int:
    """Start Mosaik again with `python`. On POSIX the current process is replaced."""
    env = dict(os.environ)
    env[ENV_RELAUNCHED] = "1"
    src_root = str(Path(__file__).resolve().parents[1])  # lets `-m mosaik` work from a checkout
    env["PYTHONPATH"] = src_root + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [python, "-m", "mosaik", *args]
    if sys.platform != "win32" and not wait:
        os.execve(python, cmd, env)  # does not return
    if wait:
        return subprocess.call(cmd, env=env)
    subprocess.Popen(cmd, env=env, **hidden_flags())
    return 0
