# Contributing to Mosaik

Thanks for helping! Bug reports, ideas and pull requests are all welcome.

## Setup

```bash
git clone https://github.com/ErickDragomir/mosaik.git && cd mosaik
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,dnd]"
ruff check .          # lint
pytest                # tests (GUI tests need a display and skip themselves otherwise)
```

Please keep the code working on **Python 3.9+** and on **Windows, macOS and Linux**: avoid
`match`, avoid `X | Y` outside annotations, use `pathlib`, and never assume a shell or a
specific path separator. The CI runs the tests on all three systems.

## Where things live

| Want to... | Look at |
|---|---|
| change how faces are found | `src/mosaik/detect.py` |
| add a new effect (blur, black box, emoji...) | `src/mosaik/effects.py` |
| change video tracking | `src/mosaik/tracking.py` |
| change how video is read/encoded | `src/mosaik/media.py` |
| change the interface | `src/mosaik/gui/` |
| change first-run installation | `src/mosaik/bootstrap.py` |

## Adding an effect

An effect is a function that edits one rectangle of the image in place:

```python
# src/mosaik/effects.py
def blur(img, area, cells):
    x1, y1, x2, y2 = area
    roi = img[y1:y2, x1:x2]
    k = max(3, (max(roi.shape[:2]) // cells) | 1)          # odd kernel size
    img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)

EFFECTS = {"mosaic": pixelate, "blur": blur}
```

Then expose it with a `--effect` option in `cli.py` and a selector in `gui/app.py`
(`Settings.effect` already carries the choice to the pipeline), and add a test in
`tests/test_effects.py`.

## Adding a detector

Any object with a `level` attribute and a `find(image, level=None)` method returning
`[(x, y, w, h, score), ...]` can replace `FaceFinder`. Build it where `FaceFinder` is created
(`cli.py` and `gui/app.py`).

## Adding a language

All user-facing text currently lives in `cli.py`, `pipeline.py`, `config.py` and `gui/`.
A pull request that moves it into a translation table (for example with `gettext`) is very
welcome — please keep English as the default.

## Pull requests

- Keep them focused and include tests for new behaviour.
- Run `ruff check .` and `pytest` before pushing.
- Describe what changed and how you tested it (which OS and Python version).
- Never add real people's photos or videos to the repository; the test portrait is a
  public-domain NASA image.
