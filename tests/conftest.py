from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"


@pytest.fixture
def face_jpg() -> Path:
    """A public-domain NASA portrait (astronaut Eileen Collins) used as a test face."""
    return DATA / "face.jpg"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never touch the real per-user data folder during tests."""
    monkeypatch.setenv("MOSAIK_HOME", str(tmp_path / "mosaik-home"))
