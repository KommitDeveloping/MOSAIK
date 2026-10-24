# Changelog

## 1.0.0

First public release.

- Mosaik censors faces with a mosaic effect in photos and videos, fully offline.
- Multi-face detection (YuNet via OpenCV) with multi-scale, tiled and rotated search.
- Video tracking: gap filling, smoothing, and extension before/after each appearance.
- Graphical interface (red & black theme, fixed-size window) with drag & drop, folder import
  and a themed built-in file browser; native file dialogs on Windows, macOS and Linux
  (zenity/kdialog).
- Command-line interface (`mosaik`).
- Automatic first-run setup in a private virtual environment; the face model is bundled.
- Audio options (remove, distort, keep) and metadata removal.
- Tested on Linux, macOS and Windows through GitHub Actions.
