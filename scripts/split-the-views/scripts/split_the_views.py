#!/usr/bin/env python3
"""split-the-views - primary CLI entrypoint.

Thin launcher: ensure the bundled `stv` package is importable, then dispatch to
stv.cli.main(). All logic lives in the stv package (see stv/__init__.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stv.cli import main

if __name__ == "__main__":
    main()
