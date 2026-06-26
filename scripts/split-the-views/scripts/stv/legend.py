"""Legend / key-box extraction: detect and crop the solid gray key panel."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

from stv.config import (
    Box,
    LEGEND_CHANNEL_TOL,
    LEGEND_GRAY_HI,
    LEGEND_GRAY_LO,
    LEGEND_MERGE_GAP,
    LEGEND_MIN_FILL_FRAC,
    LEGEND_MIN_H_FRAC,
    LEGEND_MIN_W_FRAC,
    LEGEND_PAD,
    LEGEND_SOLID_K,
)
from stv.imaging import contiguous_runs, merge_runs, solid_fill_mask, trim_empty_edges


def detect_legend_box(img: Image.Image) -> Optional[Tuple[Box, Dict[str, object]]]:
    """Detect a solid gray legend/key box. Returns (padded_box, info) or None."""
    arr = np.array(img.convert("RGB")).astype(np.int16)
    red, green, blue = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    spread = np.maximum(np.maximum(np.abs(red - green), np.abs(green - blue)), np.abs(red - blue))
    gray = (spread <= LEGEND_CHANNEL_TOL) & (red >= LEGEND_GRAY_LO) & (red <= LEGEND_GRAY_HI)

    solid = solid_fill_mask(gray, LEGEND_SOLID_K)
    if not solid.any():
        return None

    col_runs = merge_runs(contiguous_runs(solid.any(axis=0)), LEGEND_MERGE_GAP)
    if not col_runs:
        return None
    x0, x1 = max(col_runs, key=lambda run: run[1] - run[0])

    row_runs = merge_runs(contiguous_runs(solid[:, x0:x1].any(axis=1)), LEGEND_MERGE_GAP)
    if not row_runs:
        return None
    y0, y1 = max(row_runs, key=lambda run: run[1] - run[0])

    w, h = img.size
    if (x1 - x0) < int(w * LEGEND_MIN_W_FRAC) or (y1 - y0) < int(h * LEGEND_MIN_H_FRAC):
        return None

    fill_frac = float(gray[y0:y1, x0:x1].mean())
    if fill_frac < LEGEND_MIN_FILL_FRAC:
        return None

    box = (
        max(0, x0 - LEGEND_PAD),
        max(0, y0 - LEGEND_PAD),
        min(w, x1 + LEGEND_PAD),
        min(h, y1 + LEGEND_PAD),
    )
    info = {
        "method": "solid-gray-fill",
        "box_px": [int(v) for v in box],
        "fill_fraction": round(fill_frac, 4),
        "gray_range": [LEGEND_GRAY_LO, LEGEND_GRAY_HI],
    }
    return box, info


def extract_legend_from_drawing(
    img: Image.Image,
) -> Tuple[Optional[Image.Image], Optional[Box], Dict[str, object]]:
    """Crop the legend box from a drawing region. Returns (crop|None, box|None, info)."""
    found = detect_legend_box(img)
    if found is None:
        return None, None, {"detected": False}
    box, info = found
    crop = trim_empty_edges(img.crop(box), pad=4)
    info["detected"] = True
    info["legend_size_px"] = [int(crop.width), int(crop.height)]
    return crop, box, info
