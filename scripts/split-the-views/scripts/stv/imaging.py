"""Shared low-level image and array primitives used across the pipeline.

These helpers are intentionally generic (no knowledge of views, title blocks, or
legends) so detection, extraction, cleaning, and rendering can all reuse them.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from stv.config import (
    CLEAN_THRESH,
    EDGE_RULE_COVERAGE,
    EDGE_RULE_DARK_THRESH,
    EDGE_RULE_MAX_STRIP_PX,
    EDGE_RULE_SCAN_PX,
)


# -- trimming / resizing -----------------------------------------------------

def trim_empty_edges(img: Image.Image, *, threshold: int = CLEAN_THRESH, pad: int = 0) -> Image.Image:
    """Trim no-ink outer rows/columns while preserving all visible marks."""
    arr = np.array(img.convert("L"))
    mask = arr < threshold
    if not mask.any():
        return img

    ys, xs = np.where(mask)
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(img.width, int(xs.max()) + 1 + pad)
    y1 = min(img.height, int(ys.max()) + 1 + pad)
    return img.crop((x0, y0, x1, y1))


def resize_to_limit(img: Image.Image, max_px: int) -> Image.Image:
    """Downscale an image only when needed, preserving aspect ratio."""
    if max(img.size) <= max_px:
        return img

    ratio = max_px / max(img.size)
    size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
    return img.resize(size, Image.LANCZOS)


# -- edge rule / page-break artifact removal ---------------------------------

def _leading_rule_count(line_means: np.ndarray, limit: int, coverage: float) -> int:
    """Count consecutive leading lines (in scan order) that are mostly dark.

    Scans up to ``limit`` lines from the start of ``line_means``; a line counts
    while its dark fraction stays >= ``coverage``, and scanning stops at the first
    gap once any dark line has been seen. This is the single shared kernel behind
    the top/bottom/left/right edge scans (bottom/right pass a reversed view).
    """
    count = 0
    for i in range(limit):
        if float(line_means[i]) >= coverage:
            count = i + 1
        elif count:
            break
    return count


def strip_edge_rule_lines(
    img: Image.Image,
    *,
    threshold: int = EDGE_RULE_DARK_THRESH,
    coverage: float = EDGE_RULE_COVERAGE,
    scan_px: int = EDGE_RULE_SCAN_PX,
    max_strip_px: int = EDGE_RULE_MAX_STRIP_PX,
) -> Tuple[Image.Image, Dict[str, int]]:
    """Remove full-span edge rule/page-break lines from a crop.

    This is intentionally conservative: it only strips dark rows/columns that touch
    the outer edge, sit inside the first few pixels, and cover most of the crop
    width/height. The goal is to remove separator/border artifacts introduced by
    screenshot page breaks without trimming actual drawing geometry.
    """
    if img.width <= 2 or img.height <= 2:
        return img, {"top": 0, "bottom": 0, "left": 0, "right": 0}

    arr = np.array(img.convert("L"))
    dark = arr < threshold
    h, w = dark.shape

    row_mean = dark.mean(axis=1)
    col_mean = dark.mean(axis=0)
    limit_h = min(scan_px, max_strip_px, h - 1)
    limit_w = min(scan_px, max_strip_px, w - 1)

    top = _leading_rule_count(row_mean, limit_h, coverage)
    bottom = _leading_rule_count(row_mean[::-1], limit_h, coverage)
    left = _leading_rule_count(col_mean, limit_w, coverage)
    right = _leading_rule_count(col_mean[::-1], limit_w, coverage)

    x0, y0 = left, top
    x1, y1 = w - right, h - bottom
    if x1 <= x0 or y1 <= y0:
        return img, {"top": 0, "bottom": 0, "left": 0, "right": 0}

    return img.crop((x0, y0, x1, y1)), {
        "top": int(top),
        "bottom": int(bottom),
        "left": int(left),
        "right": int(right),
    }


# -- 1-D run helpers ---------------------------------------------------------

def contiguous_runs(flags: np.ndarray) -> List[Tuple[int, int]]:
    """Return [start, end) runs where a 1-D boolean array is True."""
    runs: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for i, value in enumerate(flags):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def merge_runs(runs: Sequence[Tuple[int, int]], gap: int) -> List[Tuple[int, int]]:
    """Merge [start, end) runs separated by fewer than `gap` units.

    Used so a legend box split into adjacent cells by thin white separators is
    recovered as one span rather than a series of narrow per-cell runs.
    """
    if not runs:
        return []
    ordered = sorted(runs)
    merged: List[List[int]] = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start - merged[-1][1] <= gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def solid_fill_mask(mask: np.ndarray, k: int) -> np.ndarray:
    """Return pixels whose surrounding k x k window is entirely True.

    Uses an integral image so thin (1-2 px) antialiased lines are discarded while
    solid filled rectangles survive. Marks the top-left corner of each solid window.
    """
    h, w = mask.shape
    if h < k or w < k:
        return np.zeros_like(mask, dtype=bool)
    integral = np.zeros((h + 1, w + 1), dtype=np.int32)
    integral[1:, 1:] = np.cumsum(np.cumsum(mask.astype(np.int32), axis=0), axis=1)
    window = (
        integral[k:, k:]
        - integral[:-k, k:]
        - integral[k:, :-k]
        + integral[:-k, :-k]
    )
    out = np.zeros((h, w), dtype=bool)
    out[: h - k + 1, : w - k + 1] = window == k * k
    return out
