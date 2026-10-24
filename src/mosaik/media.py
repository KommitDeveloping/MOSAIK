"""FFmpeg access: locating the binary, probing videos, decoding and building the encoder command."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np

from .config import AUDIO_FILTER, ProcessingError, Settings
from .utils import hidden_flags

_FFMPEG = None


def find_ffmpeg() -> str:
    """System FFmpeg if installed, otherwise the portable binary shipped by imageio-ffmpeg."""
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    exe = shutil.which("ffmpeg")
    if not exe:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # noqa: BLE001
            raise ProcessingError(
                "FFmpeg was not found. Install it (https://ffmpeg.org/download.html) or run "
                "'pip install imageio-ffmpeg'."
            ) from exc
    _FFMPEG = exe
    return exe


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool


def parse_probe(text: str) -> VideoInfo:
    """Read the video properties from the output of `ffmpeg -i` (ffprobe is not needed)."""
    lines = text.splitlines()
    video_line = next(
        (ln for ln in lines if "Stream #" in ln and "Video:" in ln and "attached pic" not in ln),
        None,
    )
    if video_line is None:
        raise ProcessingError("The file has no video track.")
    size = re.search(r", (\d{2,5})x(\d{2,5})", video_line)
    if not size:
        raise ProcessingError("Could not read the video resolution.")
    width, height = int(size.group(1)), int(size.group(2))

    rot = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees", text) or re.search(
        r"rotate\s*:\s*(-?\d+)", text
    )
    if rot and round(abs(float(rot.group(1)))) % 180 == 90:
        width, height = height, width  # FFmpeg applies the rotation when decoding

    rate = re.search(r"(?<![/\d.])(\d+(?:\.\d+)?) fps", video_line) or re.search(
        r"(?<![/\d.])(\d+(?:\.\d+)?) tbr", video_line
    )
    fps = float(rate.group(1)) if rate else 25.0
    if not 1 <= fps <= 240:
        fps = 25.0

    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    duration = (
        int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else 0.0
    )
    has_audio = any("Stream #" in ln and "Audio:" in ln for ln in lines)
    return VideoInfo(width, height, fps, duration, has_audio)


def probe_video(path) -> VideoInfo:
    result = subprocess.run(
        [find_ffmpeg(), "-hide_banner", "-i", str(path)],
        stdin=subprocess.DEVNULL, capture_output=True,
        text=True, encoding="utf-8", errors="replace", **hidden_flags(),
    )
    return parse_probe(result.stderr)


def read_frames(source, info: VideoInfo, stop):
    """Yield BGR frames at a constant frame rate, already rotated correctly."""
    err = tempfile.TemporaryFile()
    cmd = [
        find_ffmpeg(), "-v", "error", "-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", f"fps={info.fps:.6f}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err, **hidden_flags()
    )
    size = info.width * info.height * 3
    count = 0
    try:
        while not stop():
            buf = bytearray(size)
            view, got = memoryview(buf), 0
            while got < size:
                n = proc.stdout.readinto(view[got:])
                if not n:
                    break
                got += n
            if got < size:
                break
            count += 1
            yield np.frombuffer(buf, np.uint8).reshape(info.height, info.width, 3)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.wait()
        if count == 0 and not stop():
            err.seek(0)
            detail = err.read().decode("utf-8", "replace")[-1500:]
            err.close()
            raise ProcessingError(f"FFmpeg cannot read the video:\n{detail}")
        err.close()


def build_encode_command(source, target, info: VideoInfo, settings: Settings, frames: int):
    """FFmpeg command that reads raw frames from stdin and muxes them with the source audio."""
    use_audio = settings.audio != "mute" and info.has_audio
    cmd = [
        find_ffmpeg(), "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{info.width}x{info.height}",
        "-r", f"{info.fps:.6f}", "-i", "-",
        "-i", str(source), "-map", "0:v:0",
    ]
    if use_audio:
        cmd += ["-map", "1:a:0"]
    cmd += [
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if use_audio:
        if settings.audio == "anon":
            cmd += ["-af", AUDIO_FILTER]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    if settings.strip_metadata:
        cmd += ["-map_metadata", "-1", "-map_chapters", "-1"]
    else:
        cmd += ["-map_metadata", "1", "-map_chapters", "1"]
    cmd += ["-sn", "-dn", "-t", f"{frames / info.fps:.6f}", str(target)]
    return cmd
