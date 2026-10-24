"""Photo and video processing: detect faces, apply the effect, write the result.

No detector is perfect (very small, covered or blurry faces can be missed) and a distorted
voice does not guarantee anonymity: always check the result.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from .config import CancelledError, ProcessingError, Result, Settings
from .detect import FaceFinder
from .effects import apply_effect
from .media import build_encode_command, find_ffmpeg, probe_video, read_frames
from .tracking import build_timeline
from .utils import hidden_flags, is_photo, is_video

FULL_SEARCH_EVERY = 6  # "max" quality: complete search only every N frames, tracking fills in


def process_photo(source, target, settings: Settings, finder: FaceFinder,
                  log=None, progress=None, cancelled=None) -> Result:
    log = log or (lambda m: None)
    progress = progress or (lambda f, t: None)
    cancelled = cancelled or (lambda: False)

    # imdecode/imencode (not imread/imwrite) so paths with accents also work on Windows;
    # imdecode applies the EXIF orientation as well.
    data = np.fromfile(source, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ProcessingError(f"Cannot read the image: {source}")

    progress(0.1, "Looking for faces...")
    boxes = finder.find(img)
    if cancelled():
        raise CancelledError()
    log(f"  faces found: {len(boxes)}")
    count = apply_effect(img, boxes, settings.strength, settings.effect)

    ext = Path(target).suffix.lower()
    params = []
    if ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    elif ext == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, 95]
    ok, buf = cv2.imencode(ext, img, params)
    if not ok:
        raise ProcessingError(f"Unsupported output format: {ext}")
    tmp = Path(str(target) + ".part")
    buf.tofile(str(tmp))  # EXIF/GPS data is not rewritten: the saved file has none
    os.replace(tmp, target)
    progress(1.0, "Done")
    return Result("photo", str(target), count, 1)


def process_video(source, target, settings: Settings, finder: FaceFinder,
                  log=None, progress=None, cancelled=None) -> Result:
    """Two passes: 1) detect and follow the faces over the whole video; 2) apply and encode."""
    log = log or (lambda m: None)
    progress = progress or (lambda f, t: None)
    cancelled = cancelled or (lambda: False)

    info = probe_video(source)
    estimate = int(info.duration * info.fps) or 0
    log(f"  video {info.width}x{info.height}, {info.fps:.2f} fps, {info.duration:.1f} s"
        f"{', with audio' if info.has_audio else ', no audio'}")

    # ---- pass 1: detection ----
    detections = []
    for idx, frame in enumerate(read_frames(source, info, cancelled)):
        level = finder.level
        if finder.level == 2 and idx % FULL_SEARCH_EVERY != 0:
            level = 1
        detections.append(finder.find(frame, level))
        if idx % 10 == 0:
            frac = min(0.99, idx / estimate) if estimate else 0.0
            progress(0.55 * frac, f"Looking for faces... frame {idx + 1}"
                     + (f"/{estimate}" if estimate else ""))
    if cancelled():
        raise CancelledError()
    n = len(detections)
    if n == 0:
        raise ProcessingError("No frames could be read.")
    timeline, faces = build_timeline(detections, info.fps)
    log(f"  frames: {n}, distinct faces followed: {faces}")

    # ---- pass 2: effect + encoding ----
    out_dir = Path(target).resolve().parent
    fd, tmp_name = tempfile.mkstemp(dir=out_dir, prefix=".mosaik_", suffix=".mp4")
    os.close(fd)
    err = tempfile.TemporaryFile()
    cmd = build_encode_command(source, tmp_name, info, settings, n)
    writer = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err, **hidden_flags()
    )
    done = 0
    try:
        for idx, frame in enumerate(read_frames(source, info, cancelled)):
            if idx >= n:
                break
            apply_effect(frame, timeline[idx], settings.strength, settings.effect)
            try:
                writer.stdin.write(frame)
            except (BrokenPipeError, OSError) as exc:
                err.seek(0)
                raise ProcessingError(
                    "FFmpeg stopped encoding:\n" + err.read().decode("utf-8", "replace")[-1500:]
                ) from exc
            done += 1
            if idx % 10 == 0:
                progress(0.55 + 0.43 * idx / n, f"Applying the effect and saving... {idx + 1}/{n}")
        if cancelled():
            raise CancelledError()
        if done < n:
            raise ProcessingError(f"Incomplete read: {done} frames out of {n}.")
        writer.stdin.close()
        if writer.wait() != 0:
            err.seek(0)
            raise ProcessingError(
                "Video encoding failed:\n" + err.read().decode("utf-8", "replace")[-1500:]
            )
        if os.path.getsize(tmp_name) == 0:
            raise ProcessingError("FFmpeg produced an empty file.")
        if sys.platform != "win32":  # mkstemp creates 0600 files: use the user's normal mode
            mask = os.umask(0)
            os.umask(mask)
            os.chmod(tmp_name, 0o666 & ~mask)
        os.replace(tmp_name, target)  # a failure never touches a pre-existing file
        progress(1.0, "Done")
        return Result("video", str(target), faces, n)
    finally:
        if writer.poll() is None:
            try:
                writer.stdin.close()
            except OSError:
                pass
            writer.kill()
            writer.wait()
        err.close()
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def process_file(source, target, settings, finder, log=None, progress=None,
                 cancelled=None) -> Result:
    if is_video(source):
        find_ffmpeg()  # fail early with a clear message
        return process_video(source, target, settings, finder, log, progress, cancelled)
    if is_photo(source):
        return process_photo(source, target, settings, finder, log, progress, cancelled)
    raise ProcessingError(f"Unsupported file type: {Path(source).suffix or source}")
