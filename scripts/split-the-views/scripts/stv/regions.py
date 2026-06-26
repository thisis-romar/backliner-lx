"""Title-block boundary detection and drawing/title-block region extraction."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw

from stv.config import (
    Box,
    DRAWING_CROP_PAD,
    TITLE_BANDS,
    TITLE_DARK_THRESH,
    TITLE_FALLBACK_RATIO,
    TITLE_MAX_RATIO,
    TITLE_MIN_BAND_HITS,
    TITLE_MIN_RATIO,
    TITLE_SEARCH_LEFT,
    TITLE_SEARCH_RIGHT,
    TITLE_SEPARATOR_PAD,
)
from stv.imaging import strip_edge_rule_lines, trim_empty_edges


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
