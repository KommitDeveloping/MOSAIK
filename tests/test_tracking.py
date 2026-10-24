from mosaik.tracking import build_timeline


def det(f, x0=100, dx=4):
    return [(x0 + f * dx, 100, 80, 100, 0.9)]


def covers(box, d):
    return box[0] <= d[0] + 1e-6 and box[1] <= d[1] + 1e-6 and box[0] + box[2] >= d[0] + d[2] - 1e-6


def test_gaps_are_filled_and_ends_extended():
    detections = [[] for _ in range(60)]
    for f in list(range(10, 21)) + list(range(27, 41)):  # missed on frames 21..26
        detections[f] = det(f)
    timeline, faces = build_timeline(detections, 25.0)
    assert faces == 1
    covered = [f for f, boxes in enumerate(timeline) if boxes]
    assert covered[0] < 10 and covered[-1] > 40       # extended before and after
    assert all(timeline[f] for f in range(covered[0], covered[-1] + 1))  # no holes


def test_box_never_smaller_than_detection():
    detections = [det(f) for f in range(30)]
    timeline, _ = build_timeline(detections, 25.0)
    for f, ds in enumerate(detections):
        assert any(covers(b, ds[0]) for b in timeline[f])


def test_crossing_faces_stay_distinct():
    detections = [[(100 + f * 3, 100, 60, 70, 0.9), (400 - f * 3, 110, 60, 70, 0.9)]
                  for f in range(40)]
    _, faces = build_timeline(detections, 25.0)
    assert faces == 2


def test_far_apart_detections_are_different_faces():
    detections = [[] for _ in range(100)]
    detections[0] = [(10, 10, 50, 50, 0.9)]
    detections[90] = [(500, 300, 50, 50, 0.9)]
    _, faces = build_timeline(detections, 25.0)
    assert faces == 2


def test_empty_video():
    timeline, faces = build_timeline([[] for _ in range(10)], 25.0)
    assert faces == 0 and all(not boxes for boxes in timeline)
