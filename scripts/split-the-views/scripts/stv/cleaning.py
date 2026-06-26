"""Clean drawings: strip the top sheet-title band and bottom view-label band."""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from stv.config import (
    Box,
    CLEAN_THRESH,
    HF_BAND_MAX_FRAC,
    HF_BAND_MAX_PX,
    HF_CLEAN_PAD,
    HF_FOOTER_ZONE_FRAC,
    HF_FRINGE_MAX_PX,
    HF_GAP_MIN_PX,
    HF_HEADER_ZONE_FRAC,
    HF_INK_THRESH,
    HF_MIN_KEEP_FRAC,
)
from stv.imaging import contiguous_runs, trim_empty_edges


def strip_header_footer(
    img: Image.Image,
    *,
    mask_boxes: Optional[Sequence[Box]] = None,
) -> Tuple[Image.Image, Dict[str, object]]:
    """Remove a top sheet-title band and a bottom view-label band from a drawing crop.

    The rules are deliberately conservative. A band is removed only when it is:
      - separated from the drawing body by a clean whitespace gap (HF_GAP_MIN_PX);
      - thin relative to the crop (a text label, not drawing geometry);
      - located in the outer header/footer zone of the crop.
    Optional mask_boxes (e.g. a detected legend) are painted white before detection,
    so a corner key-box does not anchor the footer band. If stripping would remove
    too much of the crop, the original is returned unchanged.
    """
    work = img.convert("RGB")
    if mask_boxes:
        arr = np.array(work)
        for (x0, y0, x1, y1) in mask_boxes:
            arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1), :] = 255
        work = Image.fromarray(arr)

    gray = np.array(work.convert("L"))
    row_ink = (gray < HF_INK_THRESH).sum(axis=1)
    h = len(row_ink)
    band_max = max(HF_BAND_MAX_PX, int(h * HF_BAND_MAX_FRAC))
    runs = contiguous_runs(row_ink > 0)

    top_cut = 0
    bottom_cut = h
    removed = {"header_px": 0, "footer_px": 0}

    if runs:
        # Header: first ink run near the top, followed by a clean gap.
        first_start, first_end = runs[0]
        gap_below = (runs[1][0] - first_end) if len(runs) > 1 else (h - first_end)
        if (
            first_start <= int(h * HF_HEADER_ZONE_FRAC)
            and (first_end - first_start) <= band_max
            and gap_below >= HF_GAP_MIN_PX
        ):
            top_cut = first_end

        # Footer: last ink run near the bottom, preceded by a clean gap.
        last_start, last_end = runs[-1]
        gap_above = (last_start - runs[-2][1]) if len(runs) > 1 else last_start
        if (
            last_end >= int(h * (1.0 - HF_FOOTER_ZONE_FRAC))
            and (last_end - last_start) <= band_max
            and gap_above >= HF_GAP_MIN_PX
        ):
            bottom_cut = last_start

    # Band detection uses a darker ink threshold than trimming, so a faint anti-alias
    # fringe can sit between the two. Advance each cut to a genuinely clean edge so no
    # ghost line of the title/label survives the later trim.
    row_min = gray.min(axis=1)
    if top_cut > 0:
        steps = 0
        while top_cut < h and row_min[top_cut] < CLEAN_THRESH and steps < HF_FRINGE_MAX_PX:
            top_cut += 1
            steps += 1
    if bottom_cut < h:
        steps = 0
        while bottom_cut > 0 and row_min[bottom_cut - 1] < CLEAN_THRESH and steps < HF_FRINGE_MAX_PX:
            bottom_cut -= 1
            steps += 1

    if bottom_cut - top_cut < int(h * HF_MIN_KEEP_FRAC):
        # Refuse to over-trim; leave the crop intact.
        top_cut, bottom_cut = 0, h
    else:
        removed["header_px"] = int(top_cut)
        removed["footer_px"] = int(h - bottom_cut)

    cut = work.crop((0, top_cut, work.width, bottom_cut))
    clean = trim_empty_edges(cut, pad=HF_CLEAN_PAD)
    removed["clean_size_px"] = [int(clean.width), int(clean.height)]
    return clean, removed
