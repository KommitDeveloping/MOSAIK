"""Constants, settings and exception types. Standard library only (safe to import anywhere)."""

from __future__ import annotations

from dataclasses import dataclass

APP_NAME = "Mosaik"

PHOTO_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})
VIDEO_EXT = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".flv"}
)

# Libraries installed automatically on first launch (see bootstrap.py).
REQUIREMENTS = ["numpy", "opencv-python-headless>=4.8", "imageio-ffmpeg"]
OPTIONAL_REQUIREMENTS = ["tkinterdnd2"]  # drag & drop; the app works without it

# Detection effort: 0 = one pass, 1 = several scales, 2 = scales + tiles + rotated image.
QUALITY = {"fast": 0, "balanced": 1, "max": 2}
SCORE_THRESHOLD = {0: 0.6, 1: 0.5, 2: 0.45}
MAX_SIDE = 3000  # longest side (px) of the images handed to the detector

# Mosaic strength: how many cells span the face (fewer cells = bigger blocks).
STRENGTH = {"light": 12, "medium": 8, "strong": 5}

AUDIO_MODES = ("mute", "anon", "keep")
DEFAULT_EFFECT = "mosaic"

AUDIO_FILTER = (
    "asetrate=44100*0.82,aresample=44100,atempo=1.2195,"
    "highpass=f=180,lowpass=f=3400,"
    "acompressor=threshold=-18dB:ratio=3:attack=5:release=80"
)

MODEL_NAME = "face_detection_yunet_2023mar.onnx"
MODEL_URLS = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_detection_yunet/" + MODEL_NAME,
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/" + MODEL_NAME,
)


class SetupError(RuntimeError):
    """The automatic installation of the dependencies failed."""


class ProcessingError(RuntimeError):
    """A processing error with a message that is meant to be shown to the user."""


class CancelledError(Exception):
    """The user cancelled the operation."""


@dataclass
class Settings:
    quality: str = "balanced"        # fast | balanced | max
    strength: str = "medium"         # light | medium | strong
    audio: str = "mute"              # mute | anon | keep   (videos only)
    strip_metadata: bool = True
    effect: str = DEFAULT_EFFECT     # see effects.EFFECTS


@dataclass
class Result:
    kind: str    # "photo" | "video"
    path: str
    faces: int   # photo: faces found; video: distinct faces followed
    frames: int = 0
