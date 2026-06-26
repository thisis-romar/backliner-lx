"""Output writers: PDF/PNG/SVG files, ZIP bundles, and manifest helpers."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from PIL import Image
from reportlab.pdfgen import canvas

from stv import __version__
from stv.config import MAX_IMG_PX, PDF_H, PDF_W, PNG_MAX_PX
from stv.imaging import resize_to_limit


# -- manifest / filename helpers ---------------------------------------------

def manifest_base(prefix: str) -> dict:
    """Return the common manifest header shared by every ZIP bundle.

    Callers add their own fields (artifact_type, view_count, items, files, view).
    Manifests are serialized with sort_keys=True, so the field set—not insertion
    order—determines the bytes on disk.
    """
    return {
        "tool": "split-the-views",
        "version": __version__,
        "package": f"split-the-views-{__version__}.zip",
        "prefix": prefix,
    }


def names(*paths: str) -> List[str]:
    """Return basenames for the truthy paths given (skips empty strings)."""
    return [Path(p).name for p in paths if p]


def ext_label(path: str) -> str:
    """Return the SUMMARY label for a path by extension."""
    return "PDF" if path.endswith(".pdf") else "PNG"


# -- image / vector writers --------------------------------------------------

def render_pdf(img: Image.Image, path: str) -> None:
    """Place the image centered on a letter-landscape PDF page."""
    rgb = resize_to_limit(img.convert("RGB"), MAX_IMG_PX)
    iw, ih = rgb.size
    scale = min(PDF_W / iw, PDF_H / ih)
    dw, dh = iw * scale, ih * scale
    x = (PDF_W - dw) / 2
    y = (PDF_H - dh) / 2

    # Stage the embed via a system temp file so a render failure cannot leave a
    # stray *.tmp.png beside the deliverable; the temp path never affects PDF bytes.
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        rgb.save(tmp)
        c = canvas.Canvas(path, pagesize=(PDF_W, PDF_H))
        c.drawImage(tmp, x, y, width=dw, height=dh)
        c.save()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def render_png(img: Image.Image, path: str) -> None:
    """Save a mobile/Photos-friendly PNG mirror."""
    rgb = resize_to_limit(img.convert("RGB"), PNG_MAX_PX)
    rgb.save(path, optimize=True)


def write_svg(svg_text: str, outdir: str, basename: str) -> str:
    """Write an SVG document and return its path."""
    svg_path = os.path.join(outdir, f"{basename}.svg")
    with open(svg_path, "w", encoding="utf-8") as handle:
        handle.write(svg_text)
    return svg_path


def write_artifact_set(img: Image.Image, outdir: str, basename: str, make_png: bool) -> Tuple[str, str]:
    """Write a PDF and optional PNG, returning paths. PNG path is empty if disabled."""
    pdf_path = os.path.join(outdir, f"{basename}.pdf")
    render_pdf(img, pdf_path)
    png_path = ""
    if make_png:
        png_path = os.path.join(outdir, f"{basename}.png")
        render_png(img, png_path)
    return pdf_path, png_path


# -- bundling ----------------------------------------------------------------

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
