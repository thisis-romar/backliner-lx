#!/usr/bin/env python3
"""Compatibility entrypoint for drawing/title-block extraction.

Injects --extract-title-blocks (unless already present), then runs the pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stv.cli import main

if __name__ == "__main__":
    if "--extract-title-blocks" not in sys.argv:
        sys.argv.append("--extract-title-blocks")
    main()
