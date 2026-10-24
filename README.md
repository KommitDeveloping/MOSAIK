# Mosaik

**Censor faces with a mosaic effect in photos and videos — entirely offline.**

Mosaik finds every face in your photos and videos and covers it with a mosaic. Nothing is
uploaded anywhere: detection and editing happen on your own computer. It works on Windows,
macOS and Linux, with a graphical interface or from the command line.

- 🖼️ **Photos and videos**, in batches (drop in a whole folder)
- 👥 **Multiple faces**, including small, sideways and partly hidden ones
- 🎞️ **Videos are tracked over time**: if the detector misses a face for a few frames, the mosaic stays on it
- 🔒 **Private**: no network needed (the face model is bundled), metadata/GPS removed by default
- 🔊 **Audio options** for videos: remove it, distort the voice, or keep it
- ⚙️ **Zero manual setup**: the first launch installs everything it needs by itself

> **Always check the result.** No face detector is perfect (very small, covered or blurry faces
> can slip through) and a distorted voice does **not** guarantee anonymity. For the safest
> output use *Maximum precision* and remove the audio.

## Quick start

You need **Python 3.9 or newer** (and `tkinter` for the graphical interface — see
[platform notes](#platform-notes)).

```bash
git clone https://github.com/ErickDragomir/mosaik.git
cd mosaik
python run.py            # on some systems: python3 run.py
```

The first launch shows a short "first run" screen while it installs OpenCV, NumPy and a
portable FFmpeg into a private environment (internet required, once). After that it starts
instantly. Nothing is installed system-wide.

Prefer a regular install?

```bash
pip install .            # adds the `mosaik` and `mosaik-gui` commands
pipx install .           # or keep it isolated with pipx
```

## Using the app

1. **Add photos and videos** — drag them onto the red drop zone, or click it to browse
   (*Add folder…* adds everything inside a folder).
2. **Choose where to save** — next to the originals (`name_mosaik.jpg` / `.mp4`) or in a folder.
   Originals are never modified or overwritten.
3. **Pick the options** and press **Start censoring**. The **Log** button shows what Mosaik is
   doing (and the details if a file fails).

| Option | What it does |
|---|---|
| Precision | *Fast* · *Balanced* · *Maximum* (slower, also looks for sideways faces and tiny ones) |
| Mosaic strength | *Light* · *Medium* · *Strong* (bigger blocks) |
| Video audio | *Remove* (safest) · *Distort voice* · *Keep original* |
| Remove metadata | Strips GPS location, date, camera model… |

### Command line

```bash
mosaik photo.jpg clip.mp4                       # results next to the originals
mosaik *.jpg -o censored/ --quality max --strength strong
mosaik video.mov --audio mute
mosaik --help
```

Run `mosaik` with no files (or `mosaik --gui file1 file2`) to open the graphical interface.
Exit codes: `0` success, `1` some file failed, `2` bad usage, `130` interrupted.

## Platform notes

| System | What you need |
|---|---|
| **Windows 10/11** | Python from [python.org](https://www.python.org/downloads/) (includes tkinter). Run `python run.py`. |
| **macOS** (Intel & Apple Silicon) | Python from [python.org](https://www.python.org/downloads/) (includes a good tkinter). With Homebrew: `brew install python-tk`. The tkinter bundled with Apple's own Python is too old to be reliable. |
| **Debian / Ubuntu / Linux Mint** | `sudo apt install python3-tk python3-venv` |
| **Fedora** | `sudo dnf install python3-tkinter` |
| **Arch / Manjaro** | `sudo pacman -S tk` |
| **openSUSE** | `sudo zypper install python3-tk` |
| **Raspberry Pi / ARM Linux** | Works with 64-bit Raspberry Pi OS (same packages as Debian). |
| **WSL / servers without a display** | Use the command line (`mosaik file.jpg`); no tkinter needed. |

Everything else is installed automatically. If a platform has no pre-built OpenCV wheel, install
OpenCV (≥ 4.8) and FFmpeg with your package manager and Mosaik will use them.

**File dialogs.** On Windows and macOS Mosaik uses the system dialogs. On Linux it uses your
desktop's dialog when `zenity` (GTK) or `kdialog` (KDE) is installed, and otherwise its own
file browser. Force one with the environment variable `MOSAIK_FILE_DIALOG=builtin` or `=system`.

## How it works

1. **Detection** — [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet),
   a small face detector run through OpenCV. Higher precision levels also search at several
   scales, in overlapping tiles, and on the rotated image.
2. **Tracking (videos)** — faces are followed from frame to frame, missed frames are interpolated
   and the motion is smoothed. A box is never smaller than what was detected.
3. **Effect** — each face area (with a margin for hair, ears and chin) is pixelated with blocks
   proportional to the face size, so it cannot be "un-pixelated".
4. **Output** — videos are re-encoded with H.264/AAC through FFmpeg; the file only replaces the
   destination when everything succeeded.

## Troubleshooting

| Problem | Fix |
|---|---|
| `tkinter` / "No module named tkinter" | Install it — see the table above — or use the command line. |
| Setup fails creating the environment | Debian/Ubuntu/Mint: `sudo apt install python3-venv python3-pip`. |
| Setup fails downloading libraries | Check your internet connection / proxy and start Mosaik again. |
| "The libraries are installed but cannot be loaded" | Delete the private environment folder (shown in the message) and restart. |
| Want to reset everything | Delete `~/.local/share/mosaik` (Linux), `~/Library/Application Support/Mosaik` (macOS) or `%LOCALAPPDATA%\Mosaik` (Windows). |
| Blurry text on a Windows high-DPI screen | Already handled; update Python if it persists. |

## Development

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,dnd]"
ruff check .
pytest
```

Project layout:

```
run.py                  start from a checkout, no install needed
src/mosaik/
  cli.py                command line (and entry point of the GUI)
  bootstrap.py          automatic first-run setup (standard library only)
  config.py utils.py    constants, settings, small helpers (standard library only)
  detect.py             face detection (swap in another detector here)
  effects.py            effects applied to faces (add new effects here)
  tracking.py           per-frame detections -> stable per-frame boxes
  media.py              FFmpeg: probing, decoding, encoding command
  pipeline.py           photo and video processing
  models.py             face model lookup (bundled, offline)
  gui/                  theme, file picker, main window
tests/                  pytest suite (runs on Linux, macOS and Windows in CI)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add an effect, a detector or a translation.

## Privacy

Mosaik makes no network connections during normal use. The only time it goes online is the
first-run installation of its libraries (through `pip`), and a model download in the unlikely
case the bundled model file is missing.

## License

MIT — see [LICENSE](LICENSE). Third-party components are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
