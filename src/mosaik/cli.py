"""Command-line interface. Without files it opens the graphical interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, bootstrap
from .config import AUDIO_MODES, QUALITY, STRENGTH, ProcessingError, SetupError
from .utils import is_supported, output_path

DISCLAIMER = (
    "Always check the result: no detector finds every face, and a distorted voice does not "
    "guarantee anonymity (use --audio mute for the safest result)."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mosaik",
        description="Censor faces with a mosaic effect in photos and videos, offline. "
        "Run without files to open the graphical interface.",
    )
    parser.add_argument("files", nargs="*", help="photos and/or videos to process")
    parser.add_argument("-o", "--output-dir", help="save results here (default: next to each original)")
    parser.add_argument("--quality", choices=list(QUALITY), default="balanced",
                        help="detection precision (default: balanced)")
    parser.add_argument("--strength", choices=list(STRENGTH), default="medium",
                        help="mosaic strength (default: medium)")
    parser.add_argument("--audio", choices=AUDIO_MODES, default="mute",
                        help="videos: mute = remove audio, anon = distort voice, keep = original")
    parser.add_argument("--keep-metadata", action="store_true",
                        help="keep metadata/chapters of videos (removed by default)")
    parser.add_argument("--model", help="path to a custom YuNet .onnx model")
    parser.add_argument("--gui", action="store_true", help="open the GUI (files are pre-loaded)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _gui(files) -> int:
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:
        print(
            f"The graphical interface is not available ({exc}).\n"
            "tkinter is missing:\n"
            "  Debian/Ubuntu/Mint: sudo apt install python3-tk\n"
            "  Fedora: sudo dnf install python3-tkinter\n"
            "  Arch/Manjaro: sudo pacman -S tk\n"
            "  macOS (Homebrew): brew install python-tk\n"
            "Or use the command line: mosaik --help",
            file=sys.stderr,
        )
        return 1
    return gui_main(files)


def _ensure_dependencies(argv) -> int | None:
    """Install the libraries on first use. Returns an exit code if the work was delegated."""
    if bootstrap.deps_ready():
        return None
    if os.environ.get(bootstrap.ENV_RELAUNCHED):
        print("ERROR: the libraries are installed but cannot be loaded.", file=sys.stderr)
        return 1
    python = bootstrap.find_ready_python()
    if python is None:
        print("First run: installing what Mosaik needs (internet required, one time only)...")
        try:
            python = bootstrap.install_environment(lambda line: print("  " + line[:120]))
        except SetupError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    return bootstrap.relaunch(python, argv, wait=True)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_parser().parse_args(argv)

    if not args.files or args.gui:
        return _gui(args.files)

    delegated = _ensure_dependencies(argv)
    if delegated is not None:
        return delegated

    from .config import Settings
    from .detect import FaceFinder
    from .models import ensure_model
    from .pipeline import process_file

    out_dir = args.output_dir
    if out_dir and not Path(out_dir).is_dir():
        print(f"ERROR: the output folder does not exist: {out_dir}", file=sys.stderr)
        return 2
    settings = Settings(quality=args.quality, strength=args.strength, audio=args.audio,
                        strip_metadata=not args.keep_metadata)
    interactive = sys.stdout.isatty()
    failed = faces = done = 0
    try:
        finder = FaceFinder(ensure_model(args.model, print), args.quality)
        for number, source in enumerate(args.files, 1):
            print(f"[{number}/{len(args.files)}] {source}")
            if not is_supported(source) or not Path(source).is_file():
                print("  skipped: not a supported file", file=sys.stderr)
                failed += 1
                continue

            def progress(fraction, text, interactive=interactive):
                if interactive:
                    print(f"\r  {fraction * 100:3.0f}%  {text[:60]:<60}", end="", flush=True)

            try:
                result = process_file(source, output_path(source, out_dir), settings, finder,
                                      log=print, progress=progress)
            except ProcessingError as exc:
                print(f"\n  ERROR: {exc}", file=sys.stderr)
                failed += 1
                continue
            if interactive:
                print()
            print(f"  saved: {result.path}")
            done += 1
            faces += result.faces
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except ProcessingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\n{done} file(s) processed, {failed} failed, {faces} face(s) censored.\n{DISCLAIMER}")
    return 1 if failed else 0
