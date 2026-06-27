"""Optional OCR of the title-block crop into structured manifest fields.

This module reads the rendered text inside an extracted title-block crop and
returns both best-effort parsed fields (sheet_title, sheet_number, scale, ...)
and the raw recognized lines. Its purpose is to hand downstream consumers the
sheet's own labels as *data* instead of forcing them to infer labels from the
drawing's visual shape.

Like the SVG (vtracer) path, OCR is an OPTIONAL capability: if tesseract /
pytesseract is unavailable, every function degrades to a skip record and the
run continues unchanged. OCR never raises into the pipeline.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from PIL import Image

from stv.config import OCR_MIN_WIDTH_PX, OCR_PSM, OCR_UPSCALE

# Canonical title-block field labels, in the order they appear on the sheet.
# (manifest_key, lowercased label as printed on the sheet)
_FIELD_LABELS = [
    ("project_name", "project name"),
    ("project_date", "project date"),
    ("job_number", "job number"),
    ("client", "client"),
    ("venue", "venue"),
    ("sheet_title", "sheet title"),
    ("sheet_number", "sheet number"),
    ("scale", "scale"),
    ("drawn_by", "drawn by"),
]

_LABEL_SET = [label for _, label in _FIELD_LABELS]


def _engine_version() -> Optional[str]:
    """Return 'tesseract X.Y.Z' if the OCR stack is importable, else None."""
    try:
        import pytesseract

        return f"tesseract {pytesseract.get_tesseract_version()}"
    except Exception:
        return None


def ocr_available() -> bool:
    """True when pytesseract and the tesseract binary are both usable."""
    return _engine_version() is not None


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _run_tesseract(img: Image.Image, upscale: int, psm: int) -> str:
    """Grayscale + Lanczos-upscale a crop and return tesseract's raw text.

    Single chokepoint for every OCR pass in this module (title block, legend
    cell, sheet header) so the upscale/grayscale/psm handling lives in one place.
    """
    import pytesseract

    w, h = img.size
    up = img.convert("L").resize(
        (max(1, w * upscale), max(1, h * upscale)), Image.LANCZOS
    )
    return pytesseract.image_to_string(up, config=f"--psm {psm}")


def _looks_like_label(value: str) -> bool:
    low = value.lower()
    return any(low.startswith(lbl) for lbl in _LABEL_SET)


def _parse_fields(lines: List[str]) -> Dict[str, str]:
    """Best-effort extraction of known title-block fields from OCR lines.

    Handles both 'Label: value' on one line and 'Label' followed by its value
    on the next line (the common stacked title-block layout).
    """
    fields: Dict[str, str] = {}
    for i, line in enumerate(lines):
        low = line.lower()
        for key, label in _FIELD_LABELS:
            if key in fields or not low.startswith(label):
                continue
            after = line[len(label):].lstrip(" :\t-")
            value = after if after else (lines[i + 1] if i + 1 < len(lines) else "")
            value = _norm(value)
            # A "value" that is itself another field label is not a real value
            # (e.g. a cut title block where the value row is missing).
            if value and not _looks_like_label(value):
                fields[key] = value
    return fields


def ocr_title_block(title_block: Image.Image) -> Dict[str, object]:
    """OCR a title-block crop into structured fields + raw lines (best effort).

    Returns one of:
      - {engine, fields{...}, raw_text_lines[...], note}   on success
      - {engine: None, skipped: ...}                       when OCR unavailable
      - {engine, error: ...}                               on any OCR failure
    Never raises.
    """
    engine = _engine_version()
    if engine is None:
        return {
            "engine": None,
            "skipped": "pytesseract/tesseract not available; install tesseract and "
                       "`pip install pytesseract` to populate title-block fields",
        }
    try:
        import pytesseract  # noqa: F401  (import guarded; _run_tesseract uses it)

        # Resolution path. Above the floor we OCR at the normal upscale. Below the
        # floor (e.g. a 108px phone-screenshot column) we no longer blanket-skip:
        # we attempt an AGGRESSIVE-upscale recovery pass first (audit F1 - readable
        # Sheet Title / Scale were being dropped), and only fall back to the skip
        # record when that recovers no parseable fields.
        from stv.config import OCR_LOWRES_UPSCALE

        low_res = title_block.width < OCR_MIN_WIDTH_PX
        upscale = OCR_LOWRES_UPSCALE if low_res else OCR_UPSCALE
        raw = _run_tesseract(title_block, upscale, OCR_PSM)
        lines = [_norm(l) for l in raw.splitlines() if _norm(l)]
        fields = _parse_fields(lines)

        if low_res and not fields:
            # Recovery found nothing usable: defer to visual reading, as before.
            return {
                "engine": engine,
                "skipped_low_res": (
                    f"title block is {title_block.width}px wide, below the ~{OCR_MIN_WIDTH_PX}px OCR "
                    f"reliability floor; an aggressive-upscale recovery pass (x{OCR_LOWRES_UPSCALE}) "
                    f"recovered no parseable fields. Read the title-block crop visually."
                ),
                "title_block_width_px": int(title_block.width),
                "fields_provenance": "visual-read-required",
                "reporting_hint": (
                    "OCR skipped: read Sheet Title, Sheet Number and Scale from the title-block "
                    "crop and report them. Do not leave readable fields blank."
                ),
            }

        result = {
            "engine": engine,
            "fields": fields,
            "raw_text_lines": lines,
            "note": "Best-effort OCR of small rendered text. Verify a value against the "
                    "title-block crop before relying on it; absent fields may indicate a "
                    "cropped title block.",
        }
        if low_res:
            # Recovered below the floor: flag provenance so downstream weights it as
            # OCR-recovered-from-low-res (still verify), not a clean hi-res read.
            result["low_res_recovered"] = True
            result["title_block_width_px"] = int(title_block.width)
            result["fields_provenance"] = (
                f"ocr-low-res-recovered (x{OCR_LOWRES_UPSCALE} upscale below the "
                f"{OCR_MIN_WIDTH_PX}px floor; verify against the crop)"
            )
        return result
    except Exception as exc:  # OCR must never break the run
        return {"engine": engine, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Legend / key-box OCR -> structured BOM (1.7.0)
# ---------------------------------------------------------------------------
# Added after an audit found a model mis-reading the legend by eye (Ayrton x8
# vs the true x6, and a dropped pole length). The tool now emits the parts list
# as data. Like all OCR here it is best-effort and degrades to a skip record.

_QTY_RE = re.compile(r"(?:qty|oty|gty|cty|aty)\s*[:.\-]?\s*(\d+)", re.IGNORECASE)


def _split_legend_cells(legend):
    """Split a legend crop into per-fixture cells on full-height divider rules.

    Returns a list of (x0, x1) column ranges. Falls back to the whole crop when
    no dividers are found.
    """
    import numpy as np

    from stv.config import LEGEND_DIVIDER_DARK_FRAC, LEGEND_OCR_CELL_MIN_W_PX

    arr = np.array(legend.convert("L"))
    w = arr.shape[1]
    dark = arr < 140
    is_div = dark.mean(axis=0) > LEGEND_DIVIDER_DARK_FRAC

    centers, run_start, prev = [], None, None
    for x in range(w):
        if is_div[x]:
            if run_start is None:
                run_start = prev = x
            else:
                prev = x
        elif run_start is not None:
            centers.append((run_start + prev) // 2)
            run_start = None
    if run_start is not None:
        centers.append((run_start + prev) // 2)

    bounds = [0] + [c for c in centers if 8 < c < w - 8] + [w]
    cells = [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if (b - a) >= LEGEND_OCR_CELL_MIN_W_PX]
    return cells or [(0, w)]


def _text_band(cell):
    """Crop a cell to its label text, excluding the symbol glyph above it.

    The fixture icon sits above the label with a blank gutter between them. That
    icon/label gutter is the SINGLE LARGEST run of near-empty rows in the cell;
    internal line-spacing gaps inside a multi-line label are shorter. We start the
    crop just below that largest gutter, which removes icon-bottom fragments (the
    "Jli"/"e_Jli_" noise above "Doughty Tank Trap" - audit F3) without clipping
    the label itself. An earlier 'last gutter' heuristic over-cut multi-line
    labels; 'largest gutter' is robust to label line count.
    """
    import numpy as np

    from stv.config import LEGEND_TEXT_GUTTER_LO_FRAC, LEGEND_TEXT_GUTTER_HI_FRAC

    arr = np.array(cell.convert("L"))
    h = cell.height
    row_ink = (arr < 140).mean(axis=1)
    lo = int(h * LEGEND_TEXT_GUTTER_LO_FRAC)
    hi = int(h * LEGEND_TEXT_GUTTER_HI_FRAC)

    best_len, best_end, run, run_start = 0, lo, 0, None
    for y in range(lo, h):
        if row_ink[y] <= 0.012:
            if run_start is None:
                run_start = y
            run += 1
        else:
            if run_start is not None and run > best_len and run_start <= hi:
                best_len, best_end = run, y
            run, run_start = 0, None
    return cell.crop((0, max(0, best_end - 1), cell.width, h))


def _strip_label_noise(label):
    """Drop leading junk tokens (symbol-edge fragments) from an OCR'd label."""
    toks = [t for t in re.split(r"[^A-Za-z0-9:'\-/]+", label) if t]
    out, started = [], False
    for t in toks:
        if not started:
            # A real label word: length >= 3 with a vowel, OR any token with a digit
            # (dimension descriptors like 4' / 6' must survive).
            if (len(t) >= 3 and re.search(r"[AaEeIiOoUu]", t) and not (t.islower() and len(t) <= 3)) \
                    or re.search(r"\d", t):
                started = True
            else:
                continue
        out.append(t)
    return " ".join(out) if out else " ".join(toks)


def _parse_legend_cell(raw):
    """Parse one cell's OCR text into {label, entries:[{descriptor, qty}], raw}."""
    flat = _norm(raw)
    entries, last, first_label = [], 0, None
    for m in _QTY_RE.finditer(flat):
        seg = flat[last:m.start()]
        last = m.end()
        cleaned = _strip_label_noise(seg)
        if first_label is None:
            first_label = cleaned
            descriptor = None
        else:
            # subsequent qty in the same cell -> the segment is its descriptor
            descriptor = cleaned or None
        entries.append({"descriptor": descriptor, "qty": int(m.group(1))})
    return {"label": first_label or _strip_label_noise(flat), "entries": entries, "raw": flat}


def ocr_legend(legend):
    """OCR a legend/key-box crop into a structured parts list (best effort).

    Returns one of:
      - {engine, cells_detected, items[...], note}     on success
      - {engine: None, skipped: ...}                    when OCR unavailable
      - {engine, skipped_low_res: ...}                  when the crop is too small
      - {engine, error: ...}                            on any OCR failure
    Never raises.
    """
    engine = _engine_version()
    if engine is None:
        return {"engine": None, "skipped": "pytesseract/tesseract not available"}

    from stv.config import LEGEND_OCR_MIN_WIDTH_PX, LEGEND_OCR_PSM, LEGEND_OCR_UPSCALE

    if legend.width < LEGEND_OCR_MIN_WIDTH_PX:
        return {
            "engine": engine,
            "skipped_low_res": (
                f"legend is {legend.width}px wide, below the ~{LEGEND_OCR_MIN_WIDTH_PX}px floor; "
                f"read the quantities from the legend crop visually."
            ),
            "legend_width_px": int(legend.width),
        }

    try:
        import pytesseract

        items = []
        cells = _split_legend_cells(legend)
        for (x0, x1) in cells:
            band = _text_band(legend.crop((x0, 0, x1, legend.height)))
            raw = _run_tesseract(band, LEGEND_OCR_UPSCALE, LEGEND_OCR_PSM)
            parsed = _parse_legend_cell(raw)
            if parsed["label"] or parsed["entries"]:
                items.append(parsed)
        return {
            "engine": engine,
            "cells_detected": len(cells),
            "items": items,
            "note": (
                "Best-effort OCR of the key box. Quantities are read directly; label text may "
                "carry minor glyph noise from the adjacent symbol. Verify against the legend crop."
            ),
        }
    except Exception as exc:  # OCR must never break the run
        return {"engine": engine, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Sheet-header OCR -> regional variant (1.8.0, audit F2)
# ---------------------------------------------------------------------------
# The top-left banner ("TOURIST US 2026 - SMALL RIG" vs "TOURIST UK/EU 2026 -
# SMALL RIG") distinguishes regional variants. The prior run collapsed the set
# to one region because this banner was never read. ocr_sheet_header emits it
# as data. Best-effort; degrades to a skip record like every OCR pass here.

# Region tokens, longest/most-specific first so "UK/EU" wins over a bare "EU".
_REGION_PATTERNS = [
    ("UK/EU", re.compile(r"\bUK\s*/\s*EU\b", re.IGNORECASE)),
    ("UK", re.compile(r"\bUK\b", re.IGNORECASE)),
    ("EU", re.compile(r"\bEU\b", re.IGNORECASE)),
    ("US", re.compile(r"\bUS\b", re.IGNORECASE)),
]


def _parse_region(text: str) -> Optional[str]:
    for name, pat in _REGION_PATTERNS:
        if pat.search(text):
            return name
    return None


def ocr_sheet_header(header: Image.Image) -> Dict[str, object]:
    """OCR the top-left sheet-header banner into {text, regional_variant} (best effort).

    Returns one of:
      - {engine, text, regional_variant, raw}   on success
      - {engine: None, skipped: ...}             when OCR unavailable
      - {engine, error: ...}                     on any OCR failure
    Never raises.
    """
    engine = _engine_version()
    if engine is None:
        return {"engine": None, "skipped": "pytesseract/tesseract not available"}

    from stv.config import HEADER_OCR_PSM, HEADER_OCR_UPSCALE

    try:
        raw = _run_tesseract(header, HEADER_OCR_UPSCALE, HEADER_OCR_PSM)
        text = _norm(raw.replace("\n", " "))
        return {
            "engine": engine,
            "text": text,
            "regional_variant": _parse_region(text),
            "raw": raw.strip(),
            "note": "Best-effort OCR of the top-left banner; verify the regional variant against the crop.",
        }
    except Exception as exc:  # OCR must never break the run
        return {"engine": engine, "error": f"{type(exc).__name__}: {exc}"}
