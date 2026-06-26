#!/usr/bin/env python3
"""Compatibility entrypoint retained for packages that previously used Sheetwright."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stv.cli import main

if __name__ == "__main__":
    main()
