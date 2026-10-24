"""Effects applied to detected faces.

To add a new effect, write a function `effect(img, area, strength_cells)` that modifies
`img[y1:y2, x1:x2]` in place and register it in EFFECTS (see CONTRIBUTING.md).
"""

from __future__ import annotations

import math

import cv2

from .config import DEFAULT_EFFECT, STRENGTH, ProcessingError


def expand_box(box, width, height, margin=1.0):
    """Grow a detected box (forehead, hair, ears, chin) and clamp it to the image.

    Returns (x1, y1, x2, y2) in pixels, or None if nothing is left.
    """
    x, y, w, h = box[:4]
    x1 = x - w * 0.22 * margin
    x2 = x + w * (1 + 0.22 * margin)
    y1 = y - h * 0.38 * margin
    y2 = y + h * (1 + 0.18 * margin)
    x1, y1 = max(0, int(math.floor(x1))), max(0, int(math.floor(y1)))
    x2, y2 = min(width, int(math.ceil(x2))), min(height, int(math.ceil(y2)))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return x1, y1, x2, y2


def pixelate(img, area, cells: int) -> None:
    """Mosaic effect: pixelate `area` (x1, y1, x2, y2) of `img` in place."""
    x1, y1, x2, y2 = area
    roi = img[y1:y2, x1:x2]
    h, w = roi.shape[:2]
    block = max(3, round(max(w, h) / cells))
    small = cv2.resize(roi, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_AREA)
    img[y1:y2, x1:x2] = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


EFFECTS = {"mosaic": pixelate}


def apply_effect(img, boxes, strength: str, effect: str = DEFAULT_EFFECT) -> int:
    """Apply `effect` to every box; returns how many faces were processed."""
    try:
        func = EFFECTS[effect]
    except KeyError:
        raise ProcessingError(f"Unknown effect: {effect!r} (available: {', '.join(EFFECTS)})") from None
    height, width = img.shape[:2]
    cells = STRENGTH.get(strength, STRENGTH["medium"])
    count = 0
    for box in boxes:
        area = expand_box(box, width, height)
        if area:
            func(img, area, cells)
            count += 1
    return count
