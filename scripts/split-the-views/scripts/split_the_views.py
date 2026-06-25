#!/usr/bin/env python3
"""
split_the_views.py - split drawing-sheet views and optionally extract drawing/title-block regions.

split-the-views 1.5.0 | built 2026-06-25

Pipeline:
  1. LOAD         - read one image, one PDF, or multiple already-split PDF/PNG inputs.
  2. DETECT       - find stacked horizontal view panels when using one source image.
  3. SPLIT        - crop each view as-is; no cleaning or redrawing.
  4. EXTRACT      - optional: split each view into drawing field and title block.
  5. CLEAN        - optional: strip the sheet-title band/view-label band and pull out the legend box.
  6. VECTORIZE    - optional: trace clean drawings into scalable, layer-grouped SVGs.
  7. REVIEW       - check panel count, ink density, dimensions, and region boundary.
  8. OUTPUT       - safe PDFs, optional PNG mirrors, SVGs, master ZIPs, optional per-view ZIPs.

Filename policy:
  - ASCII lowercase only.
  - Hyphen separators only.
  - No spaces, parentheses, underscores, punctuation, emoji, or unicode.
  - View indices are zero-padded: view-01, view-02, ...
  - Region names are explicit: drawing, title-block, debug, clean, legend.
  - SVG layer names are explicit: linework, dimensions, accents.
  - ZIP members use the same safe basenames as emitted files.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tempfile
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

try:
    import fitz  # PyMuPDF, used only for PDF inputs.
except Exception:  # pragma: no cover - package remains useful for image-only runs.
    fitz = None

try:
    import vtracer  # Raster->vector tracer, used only for --svg.
except Exception:  # pragma: no cover - package remains useful without SVG export.
    vtracer = None

__version__ = "1.5.0"
__built__ = "2026-06-25"

UPLOADS_DIR = "/mnt/user-data/uploads"
OUTPUTS_DIR = "/mnt/user-data/outputs"

# View detection thresholds.
CLEAN_THRESH = 210       # A row/column has no ink if every pixel is >= this value.
MIN_SEP_H = 4            # Separator bands must be at least this many rows high.
MERGE_GAP = 12           # Nearby separator bands are clustered within this gap.
MIN_VIEW_H = 50          # Ignore short chrome fragments.
EMPTY_INK_PCT = 0.001    # Less than this ink fraction is treated as near-empty.

# Title-block detection thresholds.
TITLE_SEARCH_LEFT = 0.62       # Search starts at 62% of the view width.
TITLE_SEARCH_RIGHT = 0.985     # Ignore the outermost right border.
TITLE_MIN_RATIO = 0.055        # Title block must occupy at least this width.
TITLE_MAX_RATIO = 0.35         # Title block should not occupy more than this width.
TITLE_FALLBACK_RATIO = 0.90    # Used if detection cannot find a strong separator.
TITLE_DARK_THRESH = 185
TITLE_BANDS = 24
TITLE_MIN_BAND_HITS = 8
TITLE_SEPARATOR_PAD = 2        # Pixels removed around the separator line.

# Edge artifact cleanup for drawing-only crops.
EDGE_RULE_DARK_THRESH = 220
EDGE_RULE_COVERAGE = 0.72
EDGE_RULE_SCAN_PX = 12
EDGE_RULE_MAX_STRIP_PX = 8
DRAWING_CROP_PAD = 8

# Header/footer stripping for clean drawings (sheet-title band + view-label band).
HF_INK_THRESH = 180          # Pixel darker than this counts as ink for band detection.
HF_GAP_MIN_PX = 12           # Whitespace gap (rows) that must separate a band from the drawing body.
HF_HEADER_ZONE_FRAC = 0.22   # Header band must begin within this top fraction of the crop.
HF_FOOTER_ZONE_FRAC = 0.22   # Footer band must end within this bottom fraction of the crop.
HF_BAND_MAX_FRAC = 0.16      # A removable band must be thinner than this fraction of crop height...
HF_BAND_MAX_PX = 70          # ...or thinner than this absolute pixel height (whichever is larger).
HF_MIN_KEEP_FRAC = 0.40      # Refuse to strip if it would leave less than this fraction of height.
HF_FRINGE_MAX_PX = 6         # Extend a band cut through this many faint anti-alias rows to a clean edge.
HF_CLEAN_PAD = 12            # Uniform margin around the final clean crop.

# Legend / key-box extraction (solid gray fill).
LEGEND_GRAY_LO = 208         # Lower bound of the solid gray legend fill value.
LEGEND_GRAY_HI = 248         # Upper bound of the solid gray legend fill value.
LEGEND_CHANNEL_TOL = 14      # Max per-pixel channel spread to count as neutral gray.
LEGEND_SOLID_K = 5           # Window size for the solid-fill test; discards thin antialiased lines.
LEGEND_MERGE_GAP = 30        # Merge solid-gray column/row runs separated by fewer than this many px.
LEGEND_MIN_W_FRAC = 0.16     # Legend bbox must span at least this fraction of crop width.
LEGEND_MIN_H_FRAC = 0.05     # Legend bbox must span at least this fraction of crop height.
LEGEND_MIN_FILL_FRAC = 0.35  # Detected bbox must be at least this gray-filled to qualify.
LEGEND_PAD = 6               # Padding added around the detected legend bbox.

# SVG vectorization (clean drawing -> scalable, layer-grouped SVG).
SVG_UPSCALE = 3              # Upscale factor before tracing; more pixels keep text/thin lines legible.
SVG_BG_LUM = 205            # Pixels brighter than this luminance are background and are dropped.
SVG_SAT_MIN = 35            # Min channel spread (max-min) to treat a pixel as chromatic (blue/red).
SVG_COLOR_DELTA = 20        # Dominant-channel lead required to classify a pixel as blue or red.
SVG_MIN_LAYER_PX = 50       # Skip a color layer with fewer than this many pixels.
SVG_FILTER_SPECKLE = 2      # vtracer: drop traced specks smaller than this.
SVG_CORNER_THRESHOLD = 45   # vtracer: corner sharpness; lower keeps technical corners crisp.
SVG_LENGTH_THRESHOLD = 4.0  # vtracer: minimum path segment length.
SVG_PATH_PRECISION = 8      # vtracer: coordinate precision.
# Crisp, fixed layer colors (antialiased medians wash out at upscale; CAD-convention hues).
SVG_LAYERS = (
    ("linework", "black", "#1a1a1a"),
    ("dimensions", "blue", "#3a4fd6"),
    ("accents", "red", "#e22020"),
)

# Output rendering.
PDF_W, PDF_H = 792, 612  # Letter landscape in points.
MAX_IMG_PX = 2400        # Keep ReportLab image embeds below fragile large-image limits.
PNG_MAX_PX = 2400        # Keep PNG exports iOS/mobile friendly.
PDF_INPUT_DPI = 220      # Rasterization density for PDF input pages.

IMAGE_EXTS = ("*.png", "*.PNG", "*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.webp", "*.WEBP")
PDF_EXTS = ("*.pdf", "*.PDF")
INPUT_EXTS = IMAGE_EXTS + PDF_EXTS

Box = Tuple[int, int, int, int]


# -- filename policy ---------------------------------------------------------

def safe_slug(value: str, *, fallback: str = "artifact", max_len: int = 80) -> str:
    """Return a filesystem-safe slug using the package filename policy."""
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    text = text[:max_len].strip("-")
    return text or fallback


def safe_input_stem(path: str) -> str:
    """Derive a safe default prefix from the input filename stem."""
    return safe_slug(Path(path).stem, fallback="sheet")


def safe_zip_name(prefix: str, zip_arg: str, suffix: str = "views") -> str:
    """Return a safe ZIP filename, preserving only the .zip extension."""
    if not zip_arg:
        return f"{prefix}-{suffix}.zip"
    stem = Path(zip_arg).stem
    return f"{safe_slug(stem, fallback=f'{prefix}-{suffix}')}.zip"


def unique_slugs(raw_slugs: Sequence[str], count: int) -> List[str]:
    """Sanitize and de-duplicate view slugs, then fill missing neutral slugs."""
    width = max(2, len(str(max(count, 1))))
    result: List[str] = []
    seen: Counter[str] = Counter()

    for i in range(count):
        if i < len(raw_slugs) and raw_slugs[i].strip():
            base = safe_slug(raw_slugs[i], fallback=f"view-{i + 1:0{width}d}")
        else:
            base = f"view-{i + 1:0{width}d}"

        seen[base] += 1
        slug = base if seen[base] == 1 else f"{base}-{seen[base]}"
        result.append(slug)

    return result


# -- input discovery / loading -----------------------------------------------

def find_uploaded_input() -> str:
    """Return the single input in UPLOADS_DIR, or exit with a clear message."""
    found = sorted(path for ext in INPUT_EXTS for path in glob.glob(os.path.join(UPLOADS_DIR, ext)))

    if len(found) == 1:
        return found[0]

    if not found:
        sys.exit(
            f"[split-the-views] No image/PDF found in {UPLOADS_DIR}.\n"
            "Pass --input /path/to/sheet.png explicitly."
        )

    names = [os.path.basename(path) for path in found]
    sys.exit(
        f"[split-the-views] Multiple inputs in {UPLOADS_DIR}: {names}\n"
        "Pass --input or --inputs to specify which file(s)."
    )


def open_source_as_image(path: str) -> Image.Image:
    """Open a supported source file as an RGB PIL image."""
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        if fitz is None:
            sys.exit("[split-the-views] PDF input requires PyMuPDF: pip install pymupdf")
        doc = fitz.open(path)
        if len(doc) < 1:
            sys.exit(f"[split-the-views] Empty PDF: {path}")
        page = doc[0]
        matrix = fitz.Matrix(PDF_INPUT_DPI / 72, PDF_INPUT_DPI / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        doc.close()
        return trim_empty_edges(img)

    return Image.open(path).convert("RGB")


# -- detect views -------------------------------------------------------------

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


# -- consolidate / crop -------------------------------------------------------

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

    def count_top() -> int:
        limit = min(scan_px, max_strip_px, h - 1)
        count = 0
        for y in range(limit):
            if float(dark[y, :].mean()) >= coverage:
                count = y + 1
            elif count:
                break
        return count

    def count_bottom() -> int:
        limit = min(scan_px, max_strip_px, h - 1)
        count = 0
        for offset in range(limit):
            y = h - 1 - offset
            if float(dark[y, :].mean()) >= coverage:
                count = offset + 1
            elif count:
                break
        return count

    def count_left() -> int:
        limit = min(scan_px, max_strip_px, w - 1)
        count = 0
        for x in range(limit):
            if float(dark[:, x].mean()) >= coverage:
                count = x + 1
            elif count:
                break
        return count

    def count_right() -> int:
        limit = min(scan_px, max_strip_px, w - 1)
        count = 0
        for offset in range(limit):
            x = w - 1 - offset
            if float(dark[:, x].mean()) >= coverage:
                count = offset + 1
            elif count:
                break
        return count

    top = count_top()
    bottom = count_bottom()
    left = count_left()
    right = count_right()

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


def crop_view(img: Image.Image, box: Box) -> Image.Image:
    """Crop one view, stripping only no-ink edge rows/columns."""
    x0, y0, x1, y1 = box
    return trim_empty_edges(img.crop((x0, y0, x1, y1)))


# -- title block extraction ---------------------------------------------------

def _column_band_hits(dark: np.ndarray, x: int, window: int = 1) -> Tuple[float, int]:
    """Return vertical dark fraction and band coverage for a candidate column."""
    h, w = dark.shape
    col = dark[:, max(0, x - window):min(w, x + window + 1)].any(axis=1)
    dark_frac = float(col.mean())
    hits = 0
    for band in range(TITLE_BANDS):
        y0 = int(h * band / TITLE_BANDS)
        y1 = int(h * (band + 1) / TITLE_BANDS)
        if y1 <= y0:
            continue
        # A real border/separator line should occupy a meaningful share of each band.
        if float(col[y0:y1].mean()) > 0.20:
            hits += 1
    return dark_frac, hits


def detect_title_block_start(img: Image.Image, override_x: int = 0, fallback_ratio: float = TITLE_FALLBACK_RATIO) -> Tuple[int, Dict[str, object]]:
    """Detect the x-coordinate where the right-side title block begins."""
    view = trim_empty_edges(img)
    w, h = view.size

    if override_x > 0:
        x = max(1, min(w - 1, override_x))
        return x, {"method": "manual", "x": x, "confidence": "manual"}

    arr = np.array(view.convert("L"))
    dark = arr < TITLE_DARK_THRESH

    search_left = int(w * TITLE_SEARCH_LEFT)
    search_right = int(w * TITLE_SEARCH_RIGHT)
    min_x = int(w * (1.0 - TITLE_MAX_RATIO))
    max_x = int(w * (1.0 - TITLE_MIN_RATIO))
    search_left = max(search_left, min_x)
    search_right = min(search_right, max_x)

    candidates: List[Tuple[float, int, float, int]] = []
    for x in range(search_left, search_right):
        dark_frac, hits = _column_band_hits(dark, x, window=1)
        score = (hits * 6.0) + (dark_frac * 100.0)
        if hits >= TITLE_MIN_BAND_HITS:
            candidates.append((score, x, dark_frac, hits))

    if candidates:
        candidates.sort(reverse=True)
        best_score, best_x, best_frac, best_hits = candidates[0]
        # Collapse adjacent high-scoring columns around thick/antialiased borders.
        near = [x for score, x, frac, hits in candidates if abs(x - best_x) <= 3 and score >= best_score * 0.80]
        chosen = min(near) if near else best_x
        confidence = "high" if best_hits >= int(TITLE_BANDS * 0.75) and best_frac > 0.45 else "medium"
        return chosen, {
            "method": "vertical-line-detect",
            "x": chosen,
            "confidence": confidence,
            "score": round(float(best_score), 3),
            "dark_fraction": round(float(best_frac), 4),
            "band_hits": int(best_hits),
            "search_range": [int(search_left), int(search_right)],
        }

    x = int(w * fallback_ratio)
    x = max(1, min(w - 1, x))
    return x, {
        "method": "fallback-ratio",
        "x": x,
        "confidence": "low",
        "fallback_ratio": fallback_ratio,
        "search_range": [int(search_left), int(search_right)],
    }


def make_debug_overlay(img: Image.Image, split_x: int, info: Dict[str, object]) -> Image.Image:
    """Create a lightweight review overlay showing the detected split line."""
    out = trim_empty_edges(img).convert("RGB")
    draw = ImageDraw.Draw(out)
    x = max(0, min(out.width - 1, split_x))
    # High-contrast vertical marker plus text label for review.
    for dx in (-1, 0, 1):
        draw.line((x + dx, 0, x + dx, out.height), fill=(255, 0, 0), width=1)
    label = f"title-block-start-x={x} method={info.get('method', 'unknown')} confidence={info.get('confidence', 'unknown')}"
    draw.rectangle((8, 8, min(out.width - 8, 8 + len(label) * 7), 28), fill=(255, 255, 255), outline=(255, 0, 0))
    draw.text((12, 12), label, fill=(0, 0, 0))
    return out


def extract_regions_from_view(img: Image.Image, override_x: int = 0, fallback_ratio: float = TITLE_FALLBACK_RATIO) -> Tuple[Image.Image, Image.Image, Image.Image, Dict[str, object]]:
    """Split a full view into drawing field and title block crops."""
    view = trim_empty_edges(img)
    split_x, info = detect_title_block_start(view, override_x=override_x, fallback_ratio=fallback_ratio)
    pad = TITLE_SEPARATOR_PAD

    drawing_right = max(1, split_x - pad)
    title_left = min(view.width - 1, split_x + pad)

    raw_drawing = trim_empty_edges(view.crop((0, 0, drawing_right, view.height)))
    drawing_no_rules, edge_rules = strip_edge_rule_lines(raw_drawing)
    drawing = trim_empty_edges(drawing_no_rules, pad=DRAWING_CROP_PAD)
    title_block = trim_empty_edges(view.crop((title_left, 0, view.width, view.height)))
    debug = make_debug_overlay(view, split_x, info)

    info.update({
        "view_size_px": [int(view.width), int(view.height)],
        "raw_drawing_size_px": [int(raw_drawing.width), int(raw_drawing.height)],
        "drawing_size_px": [int(drawing.width), int(drawing.height)],
        "title_block_size_px": [int(title_block.width), int(title_block.height)],
        "drawing_edge_rules_stripped_px": edge_rules,
    })
    return drawing, title_block, debug, info


# -- header/footer band stripping --------------------------------------------

def _contiguous_runs(flags: np.ndarray) -> List[Tuple[int, int]]:
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


def _merge_runs(runs: Sequence[Tuple[int, int]], gap: int) -> List[Tuple[int, int]]:
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
    runs = _contiguous_runs(row_ink > 0)

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


# -- legend / key-box extraction ---------------------------------------------

def _solid_fill_mask(mask: np.ndarray, k: int) -> np.ndarray:
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


def detect_legend_box(img: Image.Image) -> Optional[Tuple[Box, Dict[str, object]]]:
    """Detect a solid gray legend/key box. Returns (padded_box, info) or None."""
    arr = np.array(img.convert("RGB")).astype(np.int16)
    red, green, blue = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    spread = np.maximum(np.maximum(np.abs(red - green), np.abs(green - blue)), np.abs(red - blue))
    gray = (spread <= LEGEND_CHANNEL_TOL) & (red >= LEGEND_GRAY_LO) & (red <= LEGEND_GRAY_HI)

    solid = _solid_fill_mask(gray, LEGEND_SOLID_K)
    if not solid.any():
        return None

    col_runs = _merge_runs(_contiguous_runs(solid.any(axis=0)), LEGEND_MERGE_GAP)
    if not col_runs:
        return None
    x0, x1 = max(col_runs, key=lambda run: run[1] - run[0])

    row_runs = _merge_runs(_contiguous_runs(solid[:, x0:x1].any(axis=1)), LEGEND_MERGE_GAP)
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


# -- svg vectorization --------------------------------------------------------

def svg_available() -> bool:
    """Return True when the vtracer backend for --svg is importable."""
    return vtracer is not None


def _svg_color_masks(arr: np.ndarray) -> Dict[str, np.ndarray]:
    """Split an RGB array into linework/dimensions/accents boolean masks.

    Background is dropped by luminance. Chromatic pixels are routed to the blue
    (dimensions) or red (accents) layer by dominant channel; everything else
    that is not background becomes black linework. Antialiased edges fall into
    the nearest layer, which the per-layer trace then smooths.
    """
    red_c = arr[:, :, 0].astype(int)
    green_c = arr[:, :, 1].astype(int)
    blue_c = arr[:, :, 2].astype(int)
    lum = 0.299 * red_c + 0.587 * green_c + 0.114 * blue_c
    spread = np.maximum(np.maximum(red_c, green_c), blue_c) - np.minimum(np.minimum(red_c, green_c), blue_c)

    background = lum > SVG_BG_LUM
    chromatic = (~background) & (spread > SVG_SAT_MIN)
    is_blue = chromatic & (blue_c >= red_c) & (blue_c >= green_c) & ((blue_c - red_c) > SVG_COLOR_DELTA)
    is_red = chromatic & (red_c >= blue_c) & (red_c >= green_c) & ((red_c - blue_c) > SVG_COLOR_DELTA) & ((red_c - green_c) > SVG_COLOR_DELTA)
    is_black = (~background) & (~is_blue) & (~is_red)
    return {"black": is_black, "blue": is_blue, "red": is_red}


def _vtrace_binary_paths(mask: np.ndarray) -> List[str]:
    """Trace a boolean mask with vtracer and return its <path .../> element strings."""
    binary = np.where(mask[:, :, None], 0, 255).astype("uint8").repeat(3, axis=2)
    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "layer.png")
        svg_path = os.path.join(tmp, "layer.svg")
        Image.fromarray(binary).save(png_path)
        vtracer.convert_image_to_svg_py(
            png_path,
            svg_path,
            colormode="binary",
            mode="polygon",
            filter_speckle=SVG_FILTER_SPECKLE,
            corner_threshold=SVG_CORNER_THRESHOLD,
            length_threshold=SVG_LENGTH_THRESHOLD,
            path_precision=SVG_PATH_PRECISION,
        )
        return re.findall(r"<path\b[^>]*/>", Path(svg_path).read_text(encoding="utf-8"))


def _clean_path_element(tag: str, path_id: str) -> str:
    """Strip a path's own fill (group fill applies) and assign a stable id."""
    tag = re.sub(r'\sfill="[^"]*"', "", tag)
    return re.sub(r"^<path", f'<path id="{path_id}"', tag, count=1)


def _svg_header(width: int, height: int) -> str:
    """Return a responsive SVG open tag: viewBox + 100% sizing so it scales to any container."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="100%" preserveAspectRatio="xMidYMid meet">'
    )


def vectorize_to_layered_svg(
    img: Image.Image,
    *,
    upscale: int = SVG_UPSCALE,
) -> Tuple[str, Dict[str, str], Dict[str, object]]:
    """Trace a drawing crop into a scalable, layer-grouped SVG.

    Returns (master_svg, layer_svgs, info):
      - master_svg   : one SVG with linework/dimensions/accents as named <g> groups,
                       every traced contour a separately addressable <path id=...>.
      - layer_svgs   : {layer_name: standalone_svg} for each non-empty layer.
      - info         : per-layer element counts, colors, and the viewBox dimensions.
    The SVG is resolution-independent (viewBox + 100% sizing). Requires vtracer.
    """
    if vtracer is None:
        raise RuntimeError(
            "SVG export requires the 'vtracer' package. Install it with: "
            "pip install vtracer --break-system-packages"
        )

    base = img.convert("RGB")
    width_1x, height_1x = base.size
    width, height = width_1x * upscale, height_1x * upscale
    arr = np.array(base.resize((width, height), Image.LANCZOS))
    masks = _svg_color_masks(arr)
    header = _svg_header(width, height)

    layer_paths: Dict[str, List[str]] = {}
    layer_colors: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for name, key, color in SVG_LAYERS:
        mask = masks[key]
        if int(mask.sum()) < SVG_MIN_LAYER_PX:
            counts[name] = 0
            continue
        raw = _vtrace_binary_paths(mask)
        paths = [_clean_path_element(tag, f"{name}-{i:04d}") for i, tag in enumerate(raw, start=1)]
        layer_paths[name] = paths
        layer_colors[name] = color
        counts[name] = len(paths)

    def group_block(name: str) -> List[str]:
        block = [f'  <g id="layer-{name}" fill="{layer_colors[name]}">']
        block += [f"    {path}" for path in layer_paths[name]]
        block.append("  </g>")
        return block

    master_lines = [header, "  <!-- split-the-views layered scalable export -->"]
    for name, _key, _color in SVG_LAYERS:
        if counts.get(name):
            master_lines += group_block(name)
    master_lines.append("</svg>\n")
    master_svg = "\n".join(master_lines)

    layer_svgs: Dict[str, str] = {}
    for name, _key, _color in SVG_LAYERS:
        if counts.get(name):
            layer_svgs[name] = "\n".join([header, *group_block(name), "</svg>\n"])

    info = {
        "view_box": [0, 0, int(width), int(height)],
        "intrinsic_size_px": [int(width_1x), int(height_1x)],
        "upscale": int(upscale),
        "layer_element_counts": counts,
        "layer_colors": {n: layer_colors.get(n) for n, _k, _c in SVG_LAYERS if counts.get(n)},
        "total_elements": int(sum(counts.values())),
    }
    return master_svg, layer_svgs, info


# -- review ------------------------------------------------------------------

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


# -- render artifacts ---------------------------------------------------------

def resize_to_limit(img: Image.Image, max_px: int) -> Image.Image:
    """Downscale an image only when needed, preserving aspect ratio."""
    if max(img.size) <= max_px:
        return img

    ratio = max_px / max(img.size)
    size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
    return img.resize(size, Image.LANCZOS)


def render_pdf(img: Image.Image, path: str) -> None:
    """Place the image centered on a letter-landscape PDF page."""
    rgb = resize_to_limit(img.convert("RGB"), MAX_IMG_PX)
    iw, ih = rgb.size
    scale = min(PDF_W / iw, PDF_H / ih)
    dw, dh = iw * scale, ih * scale
    x = (PDF_W - dw) / 2
    y = (PDF_H - dh) / 2

    tmp = f"{path}.tmp.png"
    rgb.save(tmp)

    c = canvas.Canvas(path, pagesize=(PDF_W, PDF_H))
    c.drawImage(tmp, x, y, width=dw, height=dh)
    c.save()

    os.remove(tmp)


def render_png(img: Image.Image, path: str) -> None:
    """Save a mobile/Photos-friendly PNG mirror."""
    rgb = resize_to_limit(img.convert("RGB"), PNG_MAX_PX)
    rgb.save(path, optimize=True)


def write_zip(zip_path: str, paths: Iterable[str], manifest: Optional[dict] = None) -> str:
    """Create a ZIP bundle and return integrity status."""
    path_list = list(paths)
    manifest_path = ""
    if manifest is not None:
        manifest_path = os.path.join(os.path.dirname(zip_path), f"{Path(zip_path).stem}-manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        path_list.append(manifest_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in path_list:
            arcname = "manifest.json" if path == manifest_path else os.path.basename(path)
            archive.write(path, arcname)

    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()

    return "OK" if bad_member is None else f"CORRUPT:{bad_member}"


def write_artifact_set(img: Image.Image, outdir: str, basename: str, make_png: bool) -> Tuple[str, str]:
    """Write a PDF and optional PNG, returning paths. PNG path is empty if disabled."""
    pdf_path = os.path.join(outdir, f"{basename}.pdf")
    render_pdf(img, pdf_path)
    png_path = ""
    if make_png:
        png_path = os.path.join(outdir, f"{basename}.png")
        render_png(img, png_path)
    return pdf_path, png_path


def write_svg(svg_text: str, outdir: str, basename: str) -> str:
    """Write an SVG document and return its path."""
    svg_path = os.path.join(outdir, f"{basename}.svg")
    with open(svg_path, "w", encoding="utf-8") as handle:
        handle.write(svg_text)
    return svg_path


# -- CLI ----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Split multi-view drawing sheets and optionally extract drawing/title-block regions."
    )

    parser.add_argument(
        "--input",
        default="",
        help="Source image/PDF path. Omit to auto-detect the single file in /mnt/user-data/uploads/.",
    )
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=[],
        help="Multiple already-split source PDFs/PNGs. When supplied, each input is treated as one view.",
    )
    parser.add_argument("--outdir", default=OUTPUTS_DIR, help="Output directory.")
    parser.add_argument(
        "--prefix",
        default="",
        help="Safe filename prefix. Defaults to sanitized input filename stem.",
    )
    parser.add_argument(
        "--views",
        default="",
        help="Comma-separated view slugs, top-to-bottom. Omit unless the user named panels.",
    )
    parser.add_argument(
        "--expected",
        type=int,
        default=0,
        help="Expected view count; used for over-split consolidation/review warnings.",
    )
    parser.add_argument(
        "--zip",
        default="",
        help="View ZIP filename in --outdir. Sanitized and forced to .zip. Defaults to <prefix>-views.zip.",
    )
    parser.add_argument("--no-zip", action="store_true", help="Suppress full-view ZIP bundling.")
    parser.add_argument(
        "--png",
        action="store_true",
        help="Also export PNG mirrors for iOS Photos/mobile preview compatibility.",
    )
    parser.add_argument(
        "--extract-title-blocks",
        action="store_true",
        help="Also extract drawing fields and title blocks from each view."
    )
    parser.add_argument(
        "--strip-header-footer",
        action="store_true",
        help="Also emit clean drawings with the top sheet-title band and bottom view-label band removed."
    )
    parser.add_argument(
        "--extract-legend",
        action="store_true",
        help="Also detect and extract the gray legend/key box from each drawing as a separate artifact."
    )
    parser.add_argument(
        "--svg",
        action="store_true",
        help="Also vectorize each clean drawing into a scalable, layer-grouped SVG (implies --strip-header-footer)."
    )
    parser.add_argument(
        "--svg-layers",
        action="store_true",
        help="With --svg, also emit each SVG layer (linework/dimensions/accents) as its own standalone SVG file."
    )
    parser.add_argument(
        "--svg-upscale",
        type=int,
        default=SVG_UPSCALE,
        help="Upscale factor applied before SVG tracing. Higher keeps small text/thin lines legible. Default: 3."
    )
    parser.add_argument(
        "--title-block-start-x",
        type=int,
        default=0,
        help="Manual title-block start X in cropped-view pixels. Overrides auto-detection."
    )
    parser.add_argument(
        "--title-block-fallback-ratio",
        type=float,
        default=TITLE_FALLBACK_RATIO,
        help="Fallback split ratio when title-block separator detection fails. Default: 0.90."
    )
    parser.add_argument(
        "--debug-overlays",
        action="store_true",
        help="Export debug PNG overlays showing detected title-block split lines."
    )
    parser.add_argument(
        "--per-view-zips",
        action="store_true",
        help="When extracting title blocks, also emit one ZIP per view containing its drawing/title-block files."
    )

    return parser.parse_args()


def prepare_views(args: argparse.Namespace) -> Tuple[List[Image.Image], List[str], str]:
    """Load inputs and return view images, default slugs, and default prefix stem."""
    if args.inputs:
        sources = args.inputs
        images = [open_source_as_image(path) for path in sources]
        slugs = []
        for index, path in enumerate(sources, start=1):
            stem = safe_input_stem(path)
            # Preserve a clean view-NN slug when source filenames already include it.
            match = re.search(r"view-?0*(\d+)", stem)
            if match:
                slugs.append(f"view-{int(match.group(1)):02d}")
            else:
                slugs.append(f"view-{index:02d}")
        prefix_base = safe_input_stem(sources[0])
        prefix_base = re.sub(r"-view-?\d+.*$", "", prefix_base).strip("-") or prefix_base
        return images, slugs, prefix_base

    if not args.input:
        args.input = find_uploaded_input()

    img = open_source_as_image(args.input)
    prefix_base = safe_input_stem(args.input)

    # A PDF input is usually an already-split view package. Treat it as one view unless multiple inputs are supplied.
    if Path(args.input).suffix.lower() == ".pdf":
        return [img], ["view-01"], prefix_base

    views = detect_views(img)
    print(f"Detected {len(views)} view(s): {[(box[1], box[3]) for box in views]}")

    raw_slugs = [slug.strip() for slug in args.views.split(",") if slug.strip()]
    expected = args.expected or len(raw_slugs)

    if expected and len(views) > expected:
        before = len(views)
        views, merges = consolidate(views, expected)
        print(f"  [consolidate] {before} -> {len(views)} (merged {merges} split(s))")

    if expected and len(views) != expected:
        print(f"  [WARN] got {len(views)}, expected {expected}. Pass --expected with the correct count.")

    cropped_views = [crop_view(img, box) for box in views]
    return cropped_views, [], prefix_base


def main() -> None:
    """Run the split-the-views pipeline."""
    args = parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print(f"split-the-views {__version__} ({__built__})")
    print("Filename rules: ascii lowercase, hyphen separators, no spaces/parentheses/underscores")

    # SVG export vectorizes the clean drawing, so it requires header/footer stripping.
    # It also enables legend detection so the legend (sheet chrome) is masked out of the
    # clean drawing before tracing, keeping the clean PDF/PNG and the SVG consistent.
    if args.svg:
        args.strip_header_footer = True
        args.extract_legend = True
        if not svg_available():
            print("  [WARN] --svg requested but 'vtracer' is not installed; SVG output will be skipped.")
            print("         Install with: pip install vtracer --break-system-packages")

    view_images, detected_slugs, default_prefix = prepare_views(args)

    args.prefix = safe_slug(args.prefix, fallback=default_prefix) if args.prefix else default_prefix
    raw_slugs = [slug.strip() for slug in args.views.split(",") if slug.strip()]
    slugs = unique_slugs(raw_slugs or detected_slugs, len(view_images))
    expected = args.expected or len(raw_slugs)
    if args.inputs and expected and len(view_images) != expected:
        print(f"  [WARN] got {len(view_images)}, expected {expected}.")

    args.zip = "" if args.no_zip else safe_zip_name(args.prefix, args.zip, suffix="views")

    print(f"Prefix: {args.prefix}")
    print(f"Outdir: {args.outdir}")
    print(f"Views : {len(view_images)}")

    pdf_paths: List[str] = []
    png_paths: List[str] = []

    drawing_paths: List[str] = []
    title_block_paths: List[str] = []
    debug_paths: List[str] = []
    per_view_zip_paths: List[str] = []
    region_manifest_items: List[dict] = []

    clean_paths: List[str] = []
    legend_paths: List[str] = []
    clean_manifest_items: List[dict] = []
    legend_manifest_items: List[dict] = []

    svg_paths: List[str] = []
    svg_manifest_items: List[dict] = []
    do_svg = args.svg and svg_available()

    need_regions = args.extract_title_blocks or args.strip_header_footer or args.extract_legend

    # Emit full views, preserving v1.2.0 behavior.
    for index, (view_img, slug) in enumerate(zip(view_images, slugs), start=1):
        flag, info = review(view_img, expected, len(view_images))
        base = f"{args.prefix}-{slug}"
        pdf_path, png_path = write_artifact_set(view_img, args.outdir, base, args.png)
        pdf_paths.append(pdf_path)
        if png_path:
            png_paths.append(png_path)
            print(f"  [{flag}] {os.path.basename(pdf_path)} + {os.path.basename(png_path)}  {info}")
        else:
            print(f"  [{flag}] {os.path.basename(pdf_path)}  {info}")

        if need_regions:
            drawing, title_block, debug, region_info = extract_regions_from_view(
                view_img,
                override_x=args.title_block_start_x,
                fallback_ratio=args.title_block_fallback_ratio,
            )

            if args.extract_title_blocks:
                drawing_base = f"{args.prefix}-{slug}-drawing"
                title_base = f"{args.prefix}-{slug}-title-block"
                debug_base = f"{args.prefix}-{slug}-debug"

                drawing_pdf, drawing_png = write_artifact_set(drawing, args.outdir, drawing_base, args.png)
                title_pdf, title_png = write_artifact_set(title_block, args.outdir, title_base, args.png)
                drawing_paths.append(drawing_pdf)
                title_block_paths.append(title_pdf)
                if drawing_png:
                    drawing_paths.append(drawing_png)
                if title_png:
                    title_block_paths.append(title_png)

                debug_png = ""
                if args.debug_overlays:
                    debug_png = os.path.join(args.outdir, f"{debug_base}.png")
                    render_png(debug, debug_png)
                    debug_paths.append(debug_png)

                region_item = {
                    "view": slug,
                    "view_index": index,
                    "title_block_detection": region_info,
                    "drawing_files": [os.path.basename(drawing_pdf)] + ([os.path.basename(drawing_png)] if drawing_png else []),
                    "title_block_files": [os.path.basename(title_pdf)] + ([os.path.basename(title_png)] if title_png else []),
                }
                if debug_png:
                    region_item["debug_overlay"] = os.path.basename(debug_png)
                region_manifest_items.append(region_item)

                print(
                    f"    [extract] {slug}: split-x={region_info.get('x')} "
                    f"method={region_info.get('method')} confidence={region_info.get('confidence')} "
                    f"drawing={region_info.get('drawing_size_px')} title-block={region_info.get('title_block_size_px')}"
                )

                if args.per_view_zips:
                    per_zip = os.path.join(args.outdir, f"{args.prefix}-{slug}-regions.zip")
                    per_members = [drawing_pdf, title_pdf]
                    if drawing_png:
                        per_members.append(drawing_png)
                    if title_png:
                        per_members.append(title_png)
                    if debug_png:
                        per_members.append(debug_png)
                    per_manifest = {
                        "tool": "split-the-views",
                        "version": __version__,
                        "package": f"split-the-views-{__version__}.zip",
                        "prefix": args.prefix,
                        "view": slug,
                        "items": [region_item],
                    }
                    status = write_zip(per_zip, per_members, per_manifest)
                    per_view_zip_paths.append(per_zip)
                    print(f"    [zip] {per_zip}  ({len(per_members)} files, integrity {status})")

            # Legend extraction runs on the drawing region; its bbox also masks the footer pass.
            legend_box: Optional[Box] = None
            if args.extract_legend:
                legend_img, legend_box, legend_info = extract_legend_from_drawing(drawing)
                if legend_img is not None:
                    legend_base = f"{args.prefix}-{slug}-legend"
                    legend_pdf, legend_png = write_artifact_set(legend_img, args.outdir, legend_base, args.png)
                    legend_paths.append(legend_pdf)
                    if legend_png:
                        legend_paths.append(legend_png)
                    legend_manifest_items.append({
                        "view": slug,
                        "view_index": index,
                        "legend_detection": legend_info,
                        "legend_files": [os.path.basename(legend_pdf)] + ([os.path.basename(legend_png)] if legend_png else []),
                    })
                    print(f"    [legend] {slug}: detected box={legend_info.get('box_px')} size={legend_info.get('legend_size_px')}")
                else:
                    print(f"    [legend] {slug}: no legend detected")

            # Clean drawing: strip sheet-title band + view-label band, masking any legend first.
            if args.strip_header_footer:
                clean_img, clean_info = strip_header_footer(
                    drawing,
                    mask_boxes=[legend_box] if legend_box else None,
                )
                clean_base = f"{args.prefix}-{slug}-clean"
                clean_pdf, clean_png = write_artifact_set(clean_img, args.outdir, clean_base, args.png)
                clean_paths.append(clean_pdf)
                if clean_png:
                    clean_paths.append(clean_png)
                clean_manifest_items.append({
                    "view": slug,
                    "view_index": index,
                    "header_footer_removed": clean_info,
                    "legend_masked": bool(legend_box),
                    "clean_files": [os.path.basename(clean_pdf)] + ([os.path.basename(clean_png)] if clean_png else []),
                })
                print(
                    f"    [clean] {slug}: header-{clean_info.get('header_px')}px "
                    f"footer-{clean_info.get('footer_px')}px size={clean_info.get('clean_size_px')}"
                )

                # Vectorize the clean drawing into a scalable, layer-grouped SVG.
                if do_svg:
                    master_svg, layer_svgs, svg_info = vectorize_to_layered_svg(
                        clean_img, upscale=args.svg_upscale,
                    )
                    svg_master_path = write_svg(master_svg, args.outdir, clean_base)
                    svg_paths.append(svg_master_path)
                    layer_files = []
                    if args.svg_layers:
                        for layer_name, layer_text in layer_svgs.items():
                            layer_path = write_svg(layer_text, args.outdir, f"{args.prefix}-{slug}-{layer_name}")
                            svg_paths.append(layer_path)
                            layer_files.append(os.path.basename(layer_path))
                    svg_manifest_items.append({
                        "view": slug,
                        "view_index": index,
                        "svg_vectorization": svg_info,
                        "svg_master": os.path.basename(svg_master_path),
                        "svg_layer_files": layer_files,
                    })
                    counts = svg_info.get("layer_element_counts", {})
                    print(
                        f"    [svg] {slug}: scalable viewBox={svg_info.get('view_box')} "
                        f"elements={svg_info.get('total_elements')} "
                        f"({' '.join(f'{k}={v}' for k, v in counts.items() if v)})"
                    )

    zip_path = ""
    if args.zip:
        zip_path = os.path.join(args.outdir, args.zip)
        view_manifest = {
            "tool": "split-the-views",
            "version": __version__,
            "package": f"split-the-views-{__version__}.zip",
            "prefix": args.prefix,
            "artifact_type": "full-views",
            "view_count": len(view_images),
            "files": [os.path.basename(path) for path in (pdf_paths + png_paths)],
        }
        status = write_zip(zip_path, pdf_paths + png_paths, view_manifest)
        print(f"ZIP: {zip_path}  ({len(pdf_paths + png_paths)} files, integrity {status})")

    drawings_zip = ""
    title_blocks_zip = ""
    debug_zip = ""
    if args.extract_title_blocks:
        region_manifest = {
            "tool": "split-the-views",
            "version": __version__,
            "package": f"split-the-views-{__version__}.zip",
            "prefix": args.prefix,
            "view_count": len(view_images),
            "items": region_manifest_items,
        }
        drawings_zip = os.path.join(args.outdir, f"{args.prefix}-drawings.zip")
        title_blocks_zip = os.path.join(args.outdir, f"{args.prefix}-title-blocks.zip")
        draw_status = write_zip(drawings_zip, drawing_paths, {**region_manifest, "artifact_type": "drawings"})
        title_status = write_zip(title_blocks_zip, title_block_paths, {**region_manifest, "artifact_type": "title-blocks"})
        print(f"ZIP: {drawings_zip}  ({len(drawing_paths)} files, integrity {draw_status})")
        print(f"ZIP: {title_blocks_zip}  ({len(title_block_paths)} files, integrity {title_status})")
        if debug_paths:
            debug_zip = os.path.join(args.outdir, f"{args.prefix}-debug-overlays.zip")
            debug_status = write_zip(debug_zip, debug_paths, {**region_manifest, "artifact_type": "debug-overlays"})
            print(f"ZIP: {debug_zip}  ({len(debug_paths)} files, integrity {debug_status})")

    clean_zip = ""
    if args.strip_header_footer and clean_paths:
        clean_zip = os.path.join(args.outdir, f"{args.prefix}-clean-drawings.zip")
        clean_manifest = {
            "tool": "split-the-views",
            "version": __version__,
            "package": f"split-the-views-{__version__}.zip",
            "prefix": args.prefix,
            "artifact_type": "clean-drawings",
            "view_count": len(view_images),
            "items": clean_manifest_items,
        }
        clean_status = write_zip(clean_zip, clean_paths, clean_manifest)
        print(f"ZIP: {clean_zip}  ({len(clean_paths)} files, integrity {clean_status})")

    legends_zip = ""
    if args.extract_legend and legend_paths:
        legends_zip = os.path.join(args.outdir, f"{args.prefix}-legends.zip")
        legend_manifest = {
            "tool": "split-the-views",
            "version": __version__,
            "package": f"split-the-views-{__version__}.zip",
            "prefix": args.prefix,
            "artifact_type": "legends",
            "view_count": len(view_images),
            "items": legend_manifest_items,
        }
        legend_status = write_zip(legends_zip, legend_paths, legend_manifest)
        print(f"ZIP: {legends_zip}  ({len(legend_paths)} files, integrity {legend_status})")

    svg_zip = ""
    if do_svg and svg_paths:
        svg_zip = os.path.join(args.outdir, f"{args.prefix}-clean-svg.zip")
        svg_manifest = {
            "tool": "split-the-views",
            "version": __version__,
            "package": f"split-the-views-{__version__}.zip",
            "prefix": args.prefix,
            "artifact_type": "clean-svg",
            "view_count": len(view_images),
            "items": svg_manifest_items,
        }
        svg_status = write_zip(svg_zip, svg_paths, svg_manifest)
        print(f"ZIP: {svg_zip}  ({len(svg_paths)} files, integrity {svg_status})")

    print("Done.")

    print("\n=== SUMMARY ===")
    for path in pdf_paths:
        print(f"PDF: {path}")
    for path in png_paths:
        print(f"PNG: {path}")
    if zip_path:
        print(f"ZIP: {zip_path}")
    for path in drawing_paths:
        label = "PDF" if path.endswith(".pdf") else "PNG"
        print(f"{label}: {path}")
    for path in title_block_paths:
        label = "PDF" if path.endswith(".pdf") else "PNG"
        print(f"{label}: {path}")
    for path in debug_paths:
        print(f"PNG: {path}")
    for path in clean_paths:
        label = "PDF" if path.endswith(".pdf") else "PNG"
        print(f"{label}: {path}")
    for path in legend_paths:
        label = "PDF" if path.endswith(".pdf") else "PNG"
        print(f"{label}: {path}")
    for path in svg_paths:
        print(f"SVG: {path}")
    if drawings_zip:
        print(f"ZIP: {drawings_zip}")
    if title_blocks_zip:
        print(f"ZIP: {title_blocks_zip}")
    if debug_zip:
        print(f"ZIP: {debug_zip}")
    if clean_zip:
        print(f"ZIP: {clean_zip}")
    if legends_zip:
        print(f"ZIP: {legends_zip}")
    if svg_zip:
        print(f"ZIP: {svg_zip}")
    for path in per_view_zip_paths:
        print(f"ZIP: {path}")


if __name__ == "__main__":
    main()
