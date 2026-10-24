import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from mosaik.config import ProcessingError  # noqa: E402
from mosaik.effects import EFFECTS, apply_effect, expand_box, pixelate  # noqa: E402


def test_expand_box_grows_and_clamps():
    x1, y1, x2, y2 = expand_box((100, 100, 100, 100), 1000, 1000)
    assert x1 < 100 and y1 < 100 and x2 > 200 and y2 > 200
    x1, y1, x2, y2 = expand_box((0, 0, 50, 50), 60, 60)  # near a corner: stays inside the image
    assert (x1, y1) == (0, 0) and x2 == 60 and y2 <= 60


def test_expand_box_outside_image_is_none():
    assert expand_box((2000, 10, 50, 50), 100, 100) is None


def test_pixelate_only_touches_the_area_and_makes_blocks():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (120, 160, 3), dtype=np.uint8)
    before = img.copy()
    pixelate(img, (40, 30, 120, 90), cells=5)
    assert np.array_equal(img[:30], before[:30]) and np.array_equal(img[:, :40], before[:, :40])
    assert not np.array_equal(img[30:90, 40:120], before[30:90, 40:120])
    area = img[30:90, 40:120]
    assert len({tuple(p) for p in area.reshape(-1, 3)}) < 80  # a few flat blocks, not noise


def test_apply_effect_counts_faces_and_rejects_unknown_effect():
    img = np.zeros((100, 100, 3), np.uint8)
    assert apply_effect(img, [(10, 10, 30, 30, 0.9), (60, 60, 20, 20, 0.9)], "medium") == 2
    with pytest.raises(ProcessingError):
        apply_effect(img, [(10, 10, 30, 30, 0.9)], "medium", effect="nope")
    assert "mosaic" in EFFECTS
