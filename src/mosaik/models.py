"""Face detection model: bundled with the package, with an optional download as a fallback."""

from __future__ import annotations

import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import cv2

from .config import MODEL_NAME, MODEL_URLS, ProcessingError
from .utils import data_dir

ENV_MODEL = "MOSAIK_MODEL"


def _is_valid(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 100_000:  # rejects Git LFS pointers
            return False
        cv2.FaceDetectorYN.create(str(path), "", (320, 320))
        return True
    except (OSError, cv2.error):
        return False


def ensure_model(explicit=None, log=print) -> Path:
    """Return a usable model file.

    Order: explicit path, $MOSAIK_MODEL, the copy bundled in the package, the user's data
    folder, and finally a one-time download (the only case that needs internet).
    """
    for label, value in (("--model", explicit), (ENV_MODEL, os.environ.get(ENV_MODEL))):
        if value:
            path = Path(value).expanduser()
            if not _is_valid(path):
                raise ProcessingError(f"Invalid or missing model file ({label}): {path}")
            return path

    bundled = Path(__file__).resolve().parent / "data" / MODEL_NAME
    for candidate in (bundled, data_dir() / MODEL_NAME):
        if _is_valid(candidate):
            return candidate

    dest = data_dir() / MODEL_NAME
    # OpenCV decides the format from the extension, so the temporary file must end in .onnx.
    part = dest.with_name("download_" + MODEL_NAME)
    errors = []
    log("Downloading the face detection model (one time, ~230 KB)...")
    for url in MODEL_URLS:
        try:
            with urllib.request.urlopen(url, timeout=30) as resp, part.open("wb") as out:
                shutil.copyfileobj(resp, out)
            if _is_valid(part):
                os.replace(part, dest)
                log(f"Model saved to {dest}")
                return dest
            errors.append(f"{url}: not a valid model")
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            errors.append(f"{url}: {exc}")
    part.unlink(missing_ok=True)
    raise ProcessingError(
        "The face detection model is missing and could not be downloaded.\n"
        f"Download it from:\n{MODEL_URLS[0]}\n"
        f"and save it in {data_dir()} (or point {ENV_MODEL} / --model to it).\n\n"
        + "\n".join(errors)
    )
