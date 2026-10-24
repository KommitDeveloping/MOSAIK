# Third-party notices

Mosaik itself is released under the MIT License (see `LICENSE`). It uses the following
components:

| Component | Use | License |
|---|---|---|
| [YuNet face detection model](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) (OpenCV Zoo) | **Bundled** in `src/mosaik/data/` | MIT — full text in `src/mosaik/data/YUNET_LICENSE` |
| [OpenCV](https://opencv.org/) (`opencv-python-headless`) | Image processing and inference | Apache-2.0 |
| [NumPy](https://numpy.org/) | Arrays | BSD-3-Clause |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | Provides a portable FFmpeg binary | BSD-2-Clause |
| [FFmpeg](https://ffmpeg.org/) | Video decoding and encoding (system install or the binary above) | LGPL/GPL, depending on the build |
| [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) (optional) | Drag & drop | MIT |

These libraries are **not** redistributed in this repository (except the model file): they are
installed from PyPI on the user's machine.

The test image `tests/data/face.jpg` is a public-domain NASA photograph (astronaut Eileen
Collins), as distributed with scikit-image.
