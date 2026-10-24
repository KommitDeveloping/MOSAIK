import pytest

pytest.importorskip("numpy")

from mosaik.config import ProcessingError, Settings  # noqa: E402
from mosaik.media import VideoInfo, build_encode_command, parse_probe  # noqa: E402

BASIC = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'in.mp4':
  Duration: 00:00:05.04, start: 0.000000, bitrate: 1000 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1920x1080 [SAR 1:1 DAR 16:9], 4012 kb/s, 29.97 fps, 29.97 tbr, 30k tbn (default)
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706d), 48000 Hz, stereo, fltp, 128 kb/s (default)
"""

ROTATED = BASIC.replace("(default)\n  Stream #0:1", "(default)\n    Side data:\n      displaymatrix: rotation of -90.00 degrees\n  Stream #0:1")

COVER_ART = """  Duration: 00:03:00.00, start: 0.0, bitrate: 320 kb/s
  Stream #0:0: Audio: mp3, 44100 Hz, stereo, fltp, 320 kb/s
  Stream #0:1: Video: mjpeg (Baseline), yuvj420p, 500x500, 90k tbr, 90k tbn (attached pic)
"""


def test_basic_probe():
    info = parse_probe(BASIC)
    assert (info.width, info.height) == (1920, 1080)
    assert info.fps == pytest.approx(29.97)
    assert info.duration == pytest.approx(5.04)
    assert info.has_audio


def test_rotation_swaps_dimensions():
    info = parse_probe(ROTATED)
    assert (info.width, info.height) == (1080, 1920)


def test_cover_art_is_not_a_video():
    with pytest.raises(ProcessingError):
        parse_probe(COVER_ART)


def test_weird_frame_rate_falls_back():
    info = parse_probe(BASIC.replace("29.97 fps, 29.97 tbr", "1000 fps, 1000 tbr"))
    assert info.fps == 25.0


def info(audio=True):
    return VideoInfo(640, 360, 25.0, 4.0, audio)


def test_mute_has_no_audio_stream():
    cmd = build_encode_command("s.mp4", "o.mp4", info(), Settings(audio="mute"), 100)
    assert "-an" in cmd and "1:a:0" not in cmd


def test_anon_distorts_and_keep_does_not():
    anon = build_encode_command("s.mp4", "o.mp4", info(), Settings(audio="anon"), 100)
    keep = build_encode_command("s.mp4", "o.mp4", info(), Settings(audio="keep"), 100)
    assert "-af" in anon and "1:a:0" in anon
    assert "-af" not in keep and "1:a:0" in keep


def test_source_without_audio_never_maps_audio():
    cmd = build_encode_command("s.mp4", "o.mp4", info(audio=False), Settings(audio="keep"), 100)
    assert "1:a:0" not in cmd and "-an" in cmd


def test_metadata_option_and_duration():
    stripped = build_encode_command("s.mp4", "o.mp4", info(), Settings(strip_metadata=True), 100)
    kept = build_encode_command("s.mp4", "o.mp4", info(), Settings(strip_metadata=False), 100)
    assert stripped[stripped.index("-map_metadata") + 1] == "-1"
    assert kept[kept.index("-map_metadata") + 1] == "1"
    assert stripped[stripped.index("-t") + 1] == "4.000000"  # 100 frames at 25 fps
