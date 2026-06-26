"""Title-block cut detection and full-sheet reconstruction.

When a multi-view run produces title blocks that are shorter than the tallest
one seen, the deficit is assumed to be a screenshot crop. This module
implements the five steps to recover the complete sheet:

  Step 1 — detect_cut_blocks:
      Compare every TB crop height against the run maximum. Any crop whose
      height is < TB_CUT_FRAC of the maximum is flagged as cut, and the
      pixel deficit is recorded.

  Step 2 — identify_missing_rows:
      The cut height tells us exactly where the real pixels end. All value
      fields below that y-coordinate are absent and need reconstruction.
      (For the SYNRGY template at 810px: Sheet Title, Sheet Number, Date,
      Scale, Drawn By, and the SYNRGY logo are all below y=607.)

  Step 3 — _find_blue_chain / compute_scale:
      Locate the dominant horizontal blue dimension chain in the target and
      reference view images by scanning for the row with the most blue pixels,
      then finding tick columns by vertical extent. The scale ratio is the
      ratio of the reference scale denominator to the tick-to-tick span ratio.
      Orthographic projection principle: views depicting the same real-world
      width at the same zoom → identical tick spans → identical scale.

  Step 4 — _derive_field_overrides / reconstruct_title_block:
      Sheet Number is extracted from the slug (view-03 → "003"). Scale is the
      computed value (e.g. "1:15"). Sheet Title is inferred from the slug
      content or view position. The reconstructed block takes the real cut
      crop as the upper portion and an edited copy of the template as the
      lower portion.

  Step 5 — composite_full_sheet:
      Paste the view image (intact drawing + cut upper TB) onto a full-height
      canvas, overlay the reconstructed complete TB in the title-block column,
      then close the left and bottom sheet borders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

# TB height fraction below which the crop is flagged as cut.
TB_CUT_FRAC = 0.85

# Default font for reconstructed text; condensed matches CAD aesthetic.
_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"

# Text color measured from the reference SYNRGY template.
_TEXT_COLOR = (52, 48, 48)
_BG_COLOR = (255, 255, 255)

# Field cell bounds in a 108 x 810 title block (1-x resolution).
# Each entry: (y0, y1, x0, x1) — all inclusive.  The bounds were measured
# by scanning the reference TB for the first and last ink rows per band.
_FIELD_POSITIONS_810 = {
    "sheet_title": (614, 661, 2, 106),   # full-width value row
    "sheet_num":   (656, 686, 2,  52),   # left column
    "date":        (656, 686, 54, 106),  # right column (unchanged)
    "scale":       (683, 716, 2,  52),   # left column
    "drawn_by":    (683, 714, 54, 106),  # right column (unchanged)
}

# Slug keywords → inferred sheet title
_SLUG_TITLE_MAP = {
    "plan":  "PLAN VIEW",
    "front": "FRONT ELEVATION",
    "side":  "SIDE ELEVATION",
    "elev":  "ELEVATION",
}

# Positional defaults for 1-, 2-, or 3-view stacks.
_POSITION_TITLE_MAP = {
    (3, 1): "PLAN VIEW",
    (3, 2): "SIDE ELEVATION",
    (3, 3): "FRONT ELEVATION",
    (2, 1): "PLAN VIEW",
    (2, 2): "ELEVATION",
    (1, 1): "PLAN VIEW",
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class CutInfo:
    """Per-view reconstruction state."""
    slug: str
    index: int            # 1-based
    tb_height: int        # actual crop height
    template_height: int  # tallest TB in the run
    is_cut: bool
    missing_px: int       # template_height - tb_height
    reference_slug: str   # slug of the tallest TB (the template)


# ---------------------------------------------------------------------------
# Step 1 — detect cut title blocks
# ---------------------------------------------------------------------------

def detect_cut_blocks(
    tb_images: Sequence[Image.Image],
    slugs: Sequence[str],
) -> List[CutInfo]:
    """Compare TB heights; return one CutInfo per view.

    The tallest crop is the template reference. Any crop whose height is less
    than TB_CUT_FRAC × template_height is marked as cut.
    """
    heights = [img.height for img in tb_images]
    template_h = max(heights) if heights else 0
    ref_idx = heights.index(template_h)
    ref_slug = slugs[ref_idx] if slugs else "view-01"

    result: List[CutInfo] = []
    for i, (img, slug) in enumerate(zip(tb_images, slugs)):
        h = img.height
        is_cut = h < TB_CUT_FRAC * template_h
        result.append(CutInfo(
            slug=slug,
            index=i + 1,
            tb_height=h,
            template_height=template_h,
            is_cut=is_cut,
            missing_px=max(0, template_h - h),
            reference_slug=ref_slug,
        ))
    return result


# ---------------------------------------------------------------------------
# Step 2 — identify which rows are missing
# ---------------------------------------------------------------------------

def identify_missing_rows(info: CutInfo) -> Dict[str, Tuple[int, int, int, int]]:
    """Return the subset of _FIELD_POSITIONS that lies below the cut.

    Fields whose value area starts at y >= info.tb_height are absent and must
    be written from the template + overrides.  Fields whose area is entirely
    above the cut are already present in real pixels and must not be touched.
    """
    missing: Dict[str, Tuple[int, int, int, int]] = {}
    for name, (y0, y1, x0, x1) in _FIELD_POSITIONS_810.items():
        # Scale positions to actual template height (handles non-810 templates)
        scale = info.template_height / 810
        ay0 = int(y0 * scale)
        ay1 = int(y1 * scale)
        ax0 = int(x0 * info.template_height / 810 * (108 / 108))  # width scales too
        ax1 = int(x1 * info.template_height / 810 * (108 / 108))
        if ay0 >= info.tb_height:
            missing[name] = (ay0, ay1, ax0, ax1)
    return missing


# ---------------------------------------------------------------------------
# Step 3 — compute scale from blue dimension chains
# ---------------------------------------------------------------------------

def _find_blue_chain(img: Image.Image) -> Optional[Tuple[int, int, int]]:
    """Find the dominant horizontal blue dimension chain.

    Returns (tick_x0, tick_x1, chain_y) measured at tick centres, or None.
    Ticks are identified as columns with vertical blue extent >= 18 px in a
    ±15 px band around the row with the most blue pixels.
    """
    arr = np.array(img.convert("RGB"))
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    blue = (b > 120) & (b - r > 40) & (b - g > 25)

    row_counts = blue.sum(axis=1)
    if row_counts.max() < 50:
        return None

    chain_y = int(row_counts.argmax())
    y0 = max(0, chain_y - 15)
    y1 = min(arr.shape[0], chain_y + 15)
    col_ext = blue[y0:y1, :].sum(axis=0)
    tick_cols = np.where(col_ext >= 18)[0]

    if len(tick_cols) < 2:
        return None

    # Group contiguous tick columns, take centre of each group.
    groups: List[int] = []
    s = int(tick_cols[0]); p = int(tick_cols[0])
    for x in tick_cols[1:]:
        if x - p > 5:
            groups.append((s + p) // 2)
            s = int(x)
        p = int(x)
    groups.append((s + p) // 2)

    return groups[0], groups[-1], chain_y


def compute_scale(
    target_view: Image.Image,
    ref_view: Image.Image,
    ref_scale_denominator: int,
) -> Tuple[int, Dict[str, object]]:
    """Compute the scale denominator for target_view.

    Uses the orthographic projection principle: views depicting the same
    real-world dimension at the same zoom share identical tick-to-tick spans,
    giving the same scale. When spans differ, the ratio gives a proportional
    estimate.

    Returns (scale_denominator, info_dict).
    """
    ref_chain = _find_blue_chain(ref_view)
    tgt_chain = _find_blue_chain(target_view)

    base_info: Dict[str, object] = {
        "ref_scale": ref_scale_denominator,
        "ref_chain": ref_chain,
        "tgt_chain": tgt_chain,
    }

    if ref_chain is None or tgt_chain is None:
        return ref_scale_denominator, {
            **base_info,
            "method": "fallback-no-chain",
            "note": "one or both views have no detectable blue chain",
        }

    ref_span = ref_chain[1] - ref_chain[0]
    tgt_span = tgt_chain[1] - tgt_chain[0]

    if ref_span < 10 or tgt_span < 10:
        return ref_scale_denominator, {
            **base_info,
            "method": "fallback-short-chain",
        }

    ratio = tgt_span / ref_span

    if 0.95 <= ratio <= 1.05:
        # Spans within 5% → same scale (orthographic width match confirmed).
        return ref_scale_denominator, {
            **base_info,
            "method": "matched-spans",
            "ref_span_px": int(ref_span),
            "tgt_span_px": int(tgt_span),
            "span_ratio": round(ratio, 4),
        }

    # Spans differ: apply ratio to estimate target scale.
    scale_den = round(ref_scale_denominator / ratio)
    return scale_den, {
        **base_info,
        "method": "ratio-computed",
        "ref_span_px": int(ref_span),
        "tgt_span_px": int(tgt_span),
        "span_ratio": round(ratio, 4),
        "computed_denominator": scale_den,
    }


# ---------------------------------------------------------------------------
# Step 4 — derive field overrides and reconstruct the title block
# ---------------------------------------------------------------------------

def _infer_sheet_title(slug: str, index: int, n_views: int) -> str:
    """Infer Sheet Title from slug keywords, then view-position defaults."""
    s = slug.lower()
    for keyword, title in _SLUG_TITLE_MAP.items():
        if keyword in s:
            return title
    return _POSITION_TITLE_MAP.get((n_views, index), f"VIEW {index:02d}")


def _derive_field_overrides(
    info: CutInfo,
    scale_denominator: int,
    n_views: int,
) -> Dict[str, str]:
    """Return {field_name: value_string} for every field that needs reconstruction."""
    # Sheet Number from slug (view-03 → "003") or 1-based index.
    m = re.search(r"(\d+)$", info.slug)
    sheet_num = f"{int(m.group(1)):03d}" if m else f"{info.index:03d}"

    return {
        "sheet_title": _infer_sheet_title(info.slug, info.index, n_views),
        "sheet_num":   sheet_num,
        "scale":       f"1:{scale_denominator}",
        # date and drawn_by are identical to the template; we do not override.
    }


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, start: int = 14) -> ImageFont.FreeTypeFont:
    """Return the largest font that fits text in max_w × max_h at 1-x TB scale."""
    for sz in range(start, 4, -1):
        try:
            f = ImageFont.truetype(_FONT_PATH, sz)
            if draw.textlength(text, font=f) <= max_w and sz <= max_h:
                return f
        except OSError:
            pass
    return ImageFont.load_default()


def reconstruct_title_block(
    cut_crop: Image.Image,
    template_crop: Image.Image,
    info: CutInfo,
    overrides: Dict[str, str],
) -> Image.Image:
    """Produce a complete title-block image by splicing real + edited template.

    The cut crop supplies real pixels for y in [0, info.tb_height).
    The template crop supplies structure for y in [info.tb_height, template_h).
    Only the fields listed in `overrides` are edited; everything else (borders,
    labels, unchanged values such as Date and Drawn By) is taken verbatim
    from the template.
    """
    template_h = template_crop.height
    cut_h = info.tb_height

    # Start with a copy of the complete template (provides all borders, labels,
    # and unchanged values such as Date, Drawn By, Project Name, etc.).
    canvas = template_crop.copy().convert("RGB")

    # Paste the real cut pixels on top — this restores the genuine upper content
    # (Tourist logo, General Notes, DESIGN INTENT ONLY, revision table, all
    # project fields that are present in the real crop).
    canvas.paste(cut_crop.convert("RGB"), (0, 0))

    # Now identify which fields need to be written (those below the cut).
    missing = identify_missing_rows(info)
    d = ImageDraw.Draw(canvas)

    for field_name, (y0, y1, x0, x1) in missing.items():
        value = overrides.get(field_name)
        if value is None:
            continue  # Not in overrides; template value stands (e.g. date, drawn_by)

        cell_w = max(1, x1 - x0 - 4)
        cell_h = max(1, y1 - y0)

        # Clear the cell and render the override value.
        d.rectangle([x0, y0, x1, y1], fill=_BG_COLOR)
        font = _fit_font(d, value, cell_w, cell_h, start=14)
        d.text((x0 + 2, y0 + 1), value, font=font, fill=_TEXT_COLOR)

    return canvas


# ---------------------------------------------------------------------------
# Step 5 — composite the full sheet
# ---------------------------------------------------------------------------

def _detect_left_border(view_img: Image.Image) -> int:
    """Find the x-coordinate of the sheet's leftmost vertical border.

    Looks for a column that is dark for more than 30% of the view height.
    Falls back to x=14 (the SYNRGY template default).
    """
    arr = np.array(view_img.convert("L"))
    h, w = arr.shape
    dark = arr < 140
    for x in range(0, min(40, w)):
        if dark[:, x].mean() > 0.30:
            return x
    return 14


def composite_full_sheet(
    view_img: Image.Image,
    recon_tb: Image.Image,
    info: CutInfo,
    tb_start_x: int,
) -> Image.Image:
    """Assemble the complete sheet from the real view and reconstructed TB.

    Args:
        view_img:    The view as cropped by the pipeline (drawing + cut TB column).
        recon_tb:    The full-height reconstructed title block.
        info:        CutInfo describing this view.
        tb_start_x:  x-pixel in view_img where the TB column begins.

    Returns:
        A full-height RGB image (info.template_height tall) with:
        - The real drawing and upper TB from view_img.
        - The complete reconstructed TB in the right column.
        - Left and bottom sheet borders extended to close the frame.
    """
    view_w, view_h = view_img.size
    template_h = info.template_height

    # Create a white canvas at the full target size.
    canvas = Image.new("RGB", (view_w, template_h), "white")

    # Layer 1: paste the real view (drawing + cut upper TB).
    canvas.paste(view_img.convert("RGB"), (0, 0))

    # Layer 2: overwrite the TB column with the complete reconstruction.
    tb_w = view_w - tb_start_x
    if recon_tb.width != tb_w or recon_tb.height != template_h:
        recon_tb = recon_tb.resize((tb_w, template_h), Image.LANCZOS)
    canvas.paste(recon_tb, (tb_start_x, 0))

    # Layer 3: close the sheet borders that were lost in the crop.
    left_x = _detect_left_border(view_img)
    border_color = (35, 35, 35)
    d = ImageDraw.Draw(canvas)

    # Extend the left border downward from where the real content ends.
    d.line(
        [(left_x, view_h - 1), (left_x, template_h - 2)],
        fill=border_color, width=2,
    )
    # Draw the bottom sheet border across the full width.
    d.line(
        [(left_x, template_h - 2), (view_w - 2, template_h - 2)],
        fill=border_color, width=2,
    )

    return canvas


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def run_reconstruction(
    view_images: Sequence[Image.Image],
    tb_images: Sequence[Image.Image],
    slugs: Sequence[str],
    tb_split_xs: Sequence[int],
    ref_scale_denominator: int = 15,
) -> Dict[str, Image.Image]:
    """Run all five reconstruction steps and return completed sheet images.

    Only views with cut title blocks are reconstructed. Complete views are
    skipped silently. The returned dict maps slug → full-sheet PIL Image.

    Args:
        view_images:          Full view images (drawing + TB) from the pipeline.
        tb_images:            Title-block crops from extract_regions_from_view.
        slugs:                View slugs (e.g. ["view-01", "view-02", "view-03"]).
        tb_split_xs:          x-coordinate of the TB column start per view.
        ref_scale_denominator: Scale denominator of the reference (tallest) view.
    """
    # Step 1 — detect cut blocks.
    cut_infos = detect_cut_blocks(tb_images, slugs)

    n_views = len(view_images)
    n_cut = sum(1 for c in cut_infos if c.is_cut)
    if n_cut == 0:
        return {}

    # The reference is the tallest TB / the first non-cut view.
    ref_idx = next(
        (i for i, c in enumerate(cut_infos) if not c.is_cut),
        0,
    )
    ref_view_img = view_images[ref_idx]
    template_tb = tb_images[ref_idx]

    results: Dict[str, Image.Image] = {}

    for info, view_img, tb_img, split_x in zip(
        cut_infos, view_images, tb_images, tb_split_xs
    ):
        if not info.is_cut:
            continue

        # Step 3 — compute scale for this view.
        scale_den, scale_info = compute_scale(
            view_img, ref_view_img, ref_scale_denominator
        )

        # Step 4a — derive field values.
        overrides = _derive_field_overrides(info, scale_den, n_views)

        # Step 4b — build the reconstructed title block.
        recon_tb = reconstruct_title_block(tb_img, template_tb, info, overrides)

        # Step 5 — composite the full sheet.
        sheet = composite_full_sheet(view_img, recon_tb, info, split_x)

        results[info.slug] = sheet

        print(
            f"    [reconstruct] {info.slug}: cut={info.tb_height}px "
            f"template={info.template_height}px missing={info.missing_px}px "
            f"scale=1:{scale_den} ({scale_info['method']}) "
            f"sheet_title=\"{overrides['sheet_title']}\""
        )

    return results
