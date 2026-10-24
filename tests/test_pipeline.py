"""End-to-end tests on real media (they need the dependencies, FFmpeg and the bundled model)."""

import subprocess

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from mosaik import cli  # noqa: E402
from mosaik.config import Settings  # noqa: E402
from mosaik.detect import FaceFinder  # noqa: E402
from mosaik.media import find_ffmpeg, probe_video, read_frames  # noqa: E402
from mosaik.models import ensure_model  # noqa: E402
from mosaik.pipeline import process_photo, process_video  # noqa: E402

CANVAS = (360, 480)  # height, width
FACE_SIZE = 200
FACE_POS = (40, 150)  # y, x


@pytest.fixture(scope="module")
def finder():
    return FaceFinder(ensure_model(), "balanced")


def canvas_with_face(face_jpg):
    face = cv2.resize(cv2.imread(str(face_jpg)), (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)
    img = np.full((*CANVAS, 3), 90, np.uint8)
    y, x = FACE_POS
    img[y:y + FACE_SIZE, x:x + FACE_SIZE] = face
    return img


def make_video(path, frames_bgr, fps=15, audio=True):
    cmd = [find_ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{CANVAS[1]}x{CANVAS[0]}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in frames_bgr:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    assert proc.wait() == 0


def region_diff(a, b, region):
    y, x, h, w = region
    return float(np.abs(a[y:y + h, x:x + w].astype(int) - b[y:y + h, x:x + w].astype(int)).mean())


def test_photo_face_is_pixelated_background_is_not(tmp_path, face_jpg, finder):
    src = tmp_path / "in.jpg"
    cv2.imwrite(str(src), canvas_with_face(face_jpg))
    out = tmp_path / "out.jpg"
    result = process_photo(src, out, Settings(), finder)
    assert result.faces >= 1 and out.is_file()
    before, after = cv2.imread(str(src)), cv2.imread(str(out))
    face_area = (FACE_POS[0] + 30, FACE_POS[1] + 40, 90, 100)
    assert region_diff(before, after, face_area) > 3
    assert region_diff(before, after, (0, 0, 30, 100)) < 3  # untouched corner


def test_photo_without_faces_is_left_alone(tmp_path, finder):
    src = tmp_path / "plain.png"
    cv2.imwrite(str(src), np.full((200, 300, 3), 128, np.uint8))
    out = tmp_path / "plain_out.png"
    assert process_photo(src, out, Settings(), finder).faces == 0
    assert np.array_equal(cv2.imread(str(src)), cv2.imread(str(out)))


def test_video_roundtrip_keeps_frames_and_audio(tmp_path, face_jpg, finder):
    src = tmp_path / "in.mp4"
    make_video(src, [canvas_with_face(face_jpg)] * 15)
    out = tmp_path / "out.mp4"
    result = process_video(src, out, Settings(audio="keep", strip_metadata=True), finder)
    assert result.frames == 15 and result.faces >= 1
    info = probe_video(out)
    assert (info.width, info.height) == (CANVAS[1], CANVAS[0]) and info.has_audio
    first_in = next(read_frames(src, probe_video(src), lambda: False))
    first_out = next(read_frames(out, info, lambda: False))
    assert region_diff(first_in, first_out, (FACE_POS[0] + 30, FACE_POS[1] + 40, 90, 100)) > 3


def test_video_without_faces_and_muted(tmp_path):
    src = tmp_path / "plain.mp4"
    make_video(src, [np.full((*CANVAS, 3), 100, np.uint8)] * 10)
    out = tmp_path / "plain_out.mp4"
    finder = FaceFinder(ensure_model(), "fast")
    result = process_video(src, out, Settings(audio="mute"), finder)
    assert result.faces == 0 and result.frames == 10
    assert not probe_video(out).has_audio


def test_cli_end_to_end(tmp_path, face_jpg):
    out_dir = tmp_path / "results"
    out_dir.mkdir()
    code = cli.main([str(face_jpg), "-o", str(out_dir), "--quality", "fast"])
    assert code == 0
    assert (out_dir / "face_mosaik.jpg").is_file()


def test_cli_reports_unsupported_files(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hi")
    assert cli.main([str(bad)]) == 1
