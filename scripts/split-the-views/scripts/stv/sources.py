"""Input discovery and loading: a single image, a PDF page, or explicit inputs."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

from PIL import Image

from stv.config import INPUT_EXTS, PDF_INPUT_DPI, UPLOADS_DIR
from stv.imaging import trim_empty_edges

try:
    import fitz  # PyMuPDF, used only for PDF inputs.
except Exception:  # pragma: no cover - package remains useful for image-only runs.
    fitz = None


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
