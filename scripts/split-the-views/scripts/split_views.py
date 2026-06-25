#!/usr/bin/env python3
"""Legacy entrypoint for split-the-views."""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("split_the_views.py")), run_name="__main__")
