"""Per-panel QA: report an EMPTY/WARN/OK flag plus ink density and aspect."""

from __future__ import annotations

from typing import Tuple

import numpy as np
from PIL import Image

from stv.config import EMPTY_INK_PCT


def review(img: Image.Image, expected_count: int, actual_count: int) -> Tuple[str, dict]:
    """Return a status flag and review metadata for a cropped panel."""
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    ink_frac = float((arr < 128).sum()) / max(1, arr.size)

    info = {
        "size": f"{w}x{h}",
        "ink_%": round(ink_frac * 100, 2),
        "aspect": round(w / max(1, h), 2),
    }

    if ink_frac < EMPTY_INK_PCT:
        return "EMPTY", info
    if expected_count > 0 and actual_count != expected_count:
        return "WARN", info
    return "OK", info
