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
    # Resolution gate: a title-block column narrower than the reliability floor
    # (typical of phone screenshots) is below tesseract's usable text density.
    # Self-skip and defer to visual reading rather than emit garbled fields.
    if title_block.width < OCR_MIN_WIDTH_PX:
        return {
            "engine": engine,
            "skipped_low_res": (
                f"title block is {title_block.width}px wide, below the ~{OCR_MIN_WIDTH_PX}px OCR "
                f"reliability floor for this text density. Read the title-block crop visually "
                f"(see the SKILL.md reporting rules) instead of trusting OCR here."
            ),
            "title_block_width_px": int(title_block.width),
        }
    try:
        import pytesseract

        w, h = title_block.size
        up = title_block.convert("L").resize(
            (max(1, w * OCR_UPSCALE), max(1, h * OCR_UPSCALE)), Image.LANCZOS
        )
        raw = pytesseract.image_to_string(up, config=f"--psm {OCR_PSM}")
        lines = [_norm(l) for l in raw.splitlines() if _norm(l)]
        fields = _parse_fields(lines)
        return {
            "engine": engine,
            "fields": fields,
            "raw_text_lines": lines,
            "note": "Best-effort OCR of small rendered text. Verify a value against the "
                    "title-block crop before relying on it; absent fields may indicate a "
                    "cropped title block.",
        }
    except Exception as exc:  # OCR must never break the run
        return {"engine": engine, "error": f"{type(exc).__name__}: {exc}"}
