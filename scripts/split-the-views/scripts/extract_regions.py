#!/usr/bin/env python3
"""Compatibility entrypoint for drawing/title-block extraction."""

from pathlib import Path
import runpy
import sys

script = Path(__file__).with_name("split_the_views.py")
if "--extract-title-blocks" not in sys.argv:
    sys.argv.append("--extract-title-blocks")
runpy.run_path(str(script), run_name="__main__")
