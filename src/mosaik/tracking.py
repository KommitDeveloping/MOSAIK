"""Turn per-frame detections into stable per-frame boxes. Pure Python (no dependencies)."""

from __future__ import annotations

import math


class _Track:
    def __init__(self, frame, box):
        self.obs = {frame: box}  # frame -> (cx, cy, w, h)
        self.last = frame
        self.vx = self.vy = 0.0

    @property
    def box(self):
        return self.obs[self.last]

    def predict(self, frame):
        cx, cy, _, _ = self.box
        gap = frame - self.last
        return cx + self.vx * gap, cy + self.vy * gap

    def add(self, frame, box):
        gap = frame - self.last
        if gap <= 3:
            self.vx = 0.5 * self.vx + 0.5 * (box[0] - self.box[0]) / gap
            self.vy = 0.5 * self.vy + 0.5 * (box[1] - self.box[1]) / gap
        else:
            self.vx = self.vy = 0.0
        self.obs[frame] = box
        self.last = frame


def build_timeline(detections, fps: float):
    """From per-frame detections [(x, y, w, h, score)] to per-frame boxes [(x, y, w, h)].

    - links faces over time (even across short detection gaps);
    - interpolates the frames where the detector missed a face;
    - extends every face a little before its first and after its last appearance;
    - smooths the motion, never shrinking a box below the detected one.

    Returns (timeline, number_of_distinct_faces).
    """
    n = len(detections)
    max_gap = max(2, round(fps * 1.5))
    lead = max(1, round(fps * 0.35))
    tail = max(1, round(fps * 0.5))
    tracks: list[_Track] = []

    for f, dets in enumerate(detections):
        live = [t for t in tracks if f - t.last <= max_gap]
        pairs = []
        for ti, track in enumerate(live):
            px, py = track.predict(f)
            size = max(track.box[2], track.box[3])
            limit = 0.7 + 0.08 * min(f - track.last, 12)
            for di, d in enumerate(dets):
                cx, cy = d[0] + d[2] / 2, d[1] + d[3] / 2
                ratio = max(d[2], 1) / max(track.box[2], 1)
                dist = math.hypot(cx - px, cy - py) / size
                if dist < limit and 0.45 < ratio < 2.2:
                    pairs.append((dist, ti, di))
        used_t, used_d = set(), set()
        for _, ti, di in sorted(pairs):
            if ti in used_t or di in used_d:
                continue
            d = dets[di]
            live[ti].add(f, (d[0] + d[2] / 2, d[1] + d[3] / 2, d[2], d[3]))
            used_t.add(ti)
            used_d.add(di)
        for di, d in enumerate(dets):
            if di not in used_d:
                tracks.append(_Track(f, (d[0] + d[2] / 2, d[1] + d[3] / 2, d[2], d[3])))

    timeline: list[list] = [[] for _ in range(n)]
    for track in tracks:
        frames = sorted(track.obs)
        raw: dict[int, tuple] = {}
        for a, b in zip(frames, frames[1:] + [None]):
            raw[a] = track.obs[a]
            if b is not None and b - a > 1:
                for k in range(a + 1, b):
                    t = (k - a) / (b - a)
                    raw[k] = tuple(p + (q - p) * t for p, q in zip(track.obs[a], track.obs[b]))
        first, last = frames[0], frames[-1]

        def grow(box, g):
            return (box[0], box[1], box[2] * g, box[3] * g)

        for k in range(1, lead + 1):
            if first - k >= 0:
                raw[first - k] = grow(track.obs[first], 1.1)
        for k in range(1, tail + 1):
            if last + k < n:
                raw[last + k] = grow(track.obs[last], 1.2)

        keys = sorted(raw)
        for i, f in enumerate(keys):
            window = [raw[k] for k in keys[max(0, i - 2): i + 3]]
            cx, cy, w, h = (sum(v[j] for v in window) / len(window) for j in range(4))
            rx, ry, rw, rh = raw[f]
            x1 = min(cx - w / 2, rx - rw / 2)
            y1 = min(cy - h / 2, ry - rh / 2)
            x2 = max(cx + w / 2, rx + rw / 2)
            y2 = max(cy + h / 2, ry + rh / 2)
            timeline[f].append((x1, y1, x2 - x1, y2 - y1))
    return timeline, len(tracks)
