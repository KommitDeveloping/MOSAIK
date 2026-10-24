"""Face detection: YuNet through OpenCV, with multi-scale, tiled and rotated search.

Any object exposing `level` (int) and `find(image, level=None) -> [(x, y, w, h, score)]`
can replace FaceFinder in the pipeline, which makes it easy to plug in another detector.
"""

from __future__ import annotations

import cv2
import numpy as np

from .config import MAX_SIDE, QUALITY, SCORE_THRESHOLD, ProcessingError


def _overlap(a, b):
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area_a, area_b = a[2] * a[3], b[2] * b[3]
    return inter / (area_a + area_b - inter + 1e-9), inter / (min(area_a, area_b) + 1e-9)


def merge_boxes(boxes, iou_threshold=0.35):
    """Merge duplicates (the same face seen at several scales), keeping the best score."""
    kept: list = []
    for box in sorted(boxes, key=lambda b: -b[4]):
        for other in kept:
            iou, contained = _overlap(box, other)
            if iou > iou_threshold or contained > 0.7:
                break
        else:
            kept.append(box)
    return kept


class FaceFinder:
    """YuNet detector with a multi-scale, tiled and rotated-image search."""

    def __init__(self, model_path, quality: str = "balanced"):
        if not hasattr(cv2, "FaceDetectorYN"):
            raise ProcessingError("This OpenCV build has no face detector (need OpenCV >= 4.8).")
        self.level = QUALITY.get(quality, 1)
        self._model = str(model_path)
        self._detectors: dict = {}

    def _detector(self, level):
        thr = SCORE_THRESHOLD[level]
        if thr not in self._detectors:
            self._detectors[thr] = cv2.FaceDetectorYN.create(
                self._model, "", (320, 320), thr, 0.3, 5000
            )
        return self._detectors[thr]

    def _run(self, img, factor, level):
        h, w = img.shape[:2]
        factor = min(factor, MAX_SIDE / max(h, w))
        nw, nh = max(32, round(w * factor)), max(32, round(h * factor))
        if (nw, nh) != (w, h):
            interp = cv2.INTER_CUBIC if factor > 1 else cv2.INTER_AREA
            img = cv2.resize(img, (nw, nh), interpolation=interp)
        det = self._detector(level)
        det.setInputSize((nw, nh))
        _, faces = det.detect(np.ascontiguousarray(img))
        out = []
        if faces is None:
            return out
        sx, sy = w / nw, h / nh
        for row in faces:
            x, y, bw, bh = row[0] * sx, row[1] * sy, row[2] * sx, row[3] * sy
            if bw < 8 or bh < 8 or not 0.35 < bw / bh < 2.8:
                continue
            out.append((float(x), float(y), float(bw), float(bh), float(row[-1])))
        return out

    @staticmethod
    def _scales(level):
        return {0: [1.0], 1: [1.0, 1.6]}.get(level, [0.5, 1.0, 1.6, 2.4])

    def _tiles(self, img, level):
        h, w = img.shape[:2]
        if max(h, w) < 600:
            return []
        tw, th = int(w * 0.6), int(h * 0.6)
        out = []
        for x0 in (0, w - tw):
            for y0 in (0, h - th):
                tile = img[y0:y0 + th, x0:x0 + tw]
                factor = min(2.5, max(1.0, 1280 / max(tw, th)))
                for x, y, bw, bh, s in self._run(tile, factor, level):
                    out.append((x + x0, y + y0, bw, bh, s))
        return out

    def find(self, img, level: int | None = None):
        """Return [(x, y, w, h, score)] in the coordinates of `img`."""
        level = self.level if level is None else level
        h, w = img.shape[:2]
        boxes = []
        for factor in self._scales(level):
            boxes += self._run(img, factor, level)
        if level >= 2:
            boxes += self._tiles(img, level)
            # Sideways or upside-down faces: rotate the image and map the boxes back.
            for x, y, bw, bh, s in self._run(cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), 1.0, level):
                boxes.append((y, h - (x + bw), bh, bw, s))
            for x, y, bw, bh, s in self._run(
                cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE), 1.0, level
            ):
                boxes.append((w - (y + bh), x, bh, bw, s))
        return merge_boxes(boxes)
