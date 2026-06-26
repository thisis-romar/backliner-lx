"""View detection: locate stacked panels, consolidate over-splits, crop views."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from stv.config import Box, CLEAN_THRESH, MERGE_GAP, MIN_SEP_H, MIN_VIEW_H
from stv.imaging import trim_empty_edges


def detect_views(img: Image.Image) -> List[Box]:
    """Find view bounding boxes by locating horizontal separator bands."""
    arr = np.array(img.convert("L"))
    h, w = arr.shape

    # A separator row contains no ink anywhere across the image.
    sep_row = arr.min(axis=1) >= CLEAN_THRESH

    sep_runs: List[Tuple[int, int]] = []
    start: Optional[int] = None

    for y, is_sep in enumerate(sep_row):
        if is_sep and start is None:
            start = y
        elif not is_sep and start is not None:
            if y - start >= MIN_SEP_H:
                sep_runs.append((start, y))
            start = None

    if start is not None and h - start >= MIN_SEP_H:
        sep_runs.append((start, h))

    if not sep_runs:
        return [(0, 0, w, h)]

    clustered: List[Tuple[int, int]] = []
    for y0, y1 in sep_runs:
        if clustered and y0 - clustered[-1][1] <= MERGE_GAP:
            clustered[-1] = (clustered[-1][0], y1)
        else:
            clustered.append((y0, y1))

    views: List[Box] = []
    prev_end = 0

    for y0, y1 in clustered:
        if y0 - prev_end >= MIN_VIEW_H:
            views.append((0, prev_end, w, y0))
        prev_end = y1

    if h - prev_end >= MIN_VIEW_H:
        views.append((0, prev_end, w, h))

    return views


def consolidate(views: Sequence[Box], expected: int) -> Tuple[List[Box], int]:
    """Merge over-split views to the expected count via smallest-gap merging."""
    if expected <= 0 or len(views) <= expected:
        return list(views), 0

    boxes = sorted(views, key=lambda box: box[1])
    merges = 0

    while len(boxes) > expected:
        gaps = [boxes[i + 1][1] - boxes[i][3] for i in range(len(boxes) - 1)]
        index = gaps.index(min(gaps))
        a, b = boxes[index], boxes[index + 1]
        boxes[index] = (
            min(a[0], b[0]),
            min(a[1], b[1]),
            max(a[2], b[2]),
            max(a[3], b[3]),
        )
        del boxes[index + 1]
        merges += 1

    return boxes, merges


def crop_view(img: Image.Image, box: Box) -> Image.Image:
    """Crop one view, stripping only no-ink edge rows/columns."""
    x0, y0, x1, y1 = box
    return trim_empty_edges(img.crop((x0, y0, x1, y1)))
