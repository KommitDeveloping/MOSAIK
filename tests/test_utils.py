from pathlib import Path

import pytest

from mosaik import utils


def test_file_types():
    assert utils.is_photo("a.JPG") and utils.is_video("b.MOV")
    assert utils.is_supported("c.png") and not utils.is_supported("d.txt")


def test_output_path_never_overwrites(tmp_path):
    src = tmp_path / "holiday.jpg"
    src.write_bytes(b"x")
    first = Path(utils.output_path(src))
    assert first.name == "holiday_mosaik.jpg"
    first.write_bytes(b"x")
    assert Path(utils.output_path(src)).name == "holiday_mosaik (2).jpg"


def test_videos_are_always_written_as_mp4(tmp_path):
    assert Path(utils.output_path(tmp_path / "clip.mkv")).name == "clip_mosaik.mp4"


def test_output_dir_is_respected(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert Path(utils.output_path(tmp_path / "a.png", out)).parent == out


@pytest.mark.parametrize(("size", "text"), [(512, "512 B"), (2048, "2.0 KB"), (5 * 1024**2, "5.0 MB")])
def test_format_size(size, text):
    assert utils.format_size(size) == text


def test_data_dir_honours_override(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSAIK_HOME", str(tmp_path / "custom"))
    assert utils.data_dir() == tmp_path / "custom" and (tmp_path / "custom").is_dir()


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32", "freebsd13"])
def test_data_dir_defaults_per_platform(tmp_path, monkeypatch, platform):
    monkeypatch.delenv("MOSAIK_HOME", raising=False)
    monkeypatch.setattr(utils.sys, "platform", platform)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(utils.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    path = utils.data_dir()
    assert path.name.lower() == "mosaik" and path.is_dir()
