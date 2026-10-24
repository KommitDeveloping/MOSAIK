#!/usr/bin/env python3
"""Start Mosaik straight from a source checkout, no installation needed:

    python run.py                      # graphical interface
    python run.py photo.jpg clip.mp4   # command line

The first launch installs what Mosaik needs automatically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mosaik.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
