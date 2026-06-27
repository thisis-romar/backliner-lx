"""Pipeline orchestration: prepare inputs, process each view, assemble bundles.

The per-view work is isolated in `process_view`; `run` wires configuration,
loops the views, and writes the master ZIP bundles and the SUMMARY block. All
stdout lines and manifest contents are identical to the 1.5.0 monolith.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from stv.config import Box, OUTPUTS_DIR
from stv.cleaning import strip_header_footer
from stv.detect import consolidate, crop_view, detect_views
from stv.legend import extract_legend_from_drawing
from stv.naming import safe_input_stem, safe_slug, safe_zip_name, unique_slugs
from stv.reconstruct import run_reconstruction
from stv.regions import extract_regions_from_view
from stv.render import (
    ext_label,
    manifest_base,
    names,
    render_png,
    write_artifact_set,
    write_svg,
    write_zip,
)
from stv.review import review
from stv.sources import find_uploaded_input, open_source_as_image
from stv.vectorize import svg_available, vectorize_to_layered_svg


@dataclass
class Collectors:
    """Accumulators for every artifact path and manifest item across all views."""

    pdf_paths: List[str] = field(default_factory=list)
    png_paths: List[str] = field(default_factory=list)
    drawing_paths: List[str] = field(default_factory=list)
    title_block_paths: List[str] = field(default_factory=list)
    debug_paths: List[str] = field(default_factory=list)
    per_view_zip_paths: List[str] = field(default_factory=list)
    region_manifest_items: List[dict] = field(default_factory=list)
    clean_paths: List[str] = field(default_factory=list)
    legend_paths: List[str] = field(default_factory=list)
    clean_manifest_items: List[dict] = field(default_factory=list)
    legend_manifest_items: List[dict] = field(default_factory=list)
    svg_paths: List[str] = field(default_factory=list)
    svg_manifest_items: List[dict] = field(default_factory=list)
    # 1.7.0: title-block heights for always-on truncation detection, and legend BOM.
    tb_heights: List[int] = field(default_factory=list)
    tb_slugs: List[str] = field(default_factory=list)
    legend_bom_items: List[dict] = field(default_factory=list)
    # 1.8.0: sheet-header crops + parsed regional variant per view (audit F2).
    header_paths: List[str] = field(default_factory=list)
    header_items: List[dict] = field(default_factory=list)
    run_manifest_path: str = ""
    # In-memory data for the reconstruction pass (not persisted as files).
    recon_paths: List[str] = field(default_factory=list)
    recon_manifest_items: List[dict] = field(default_factory=list)
    _view_images: List[Image.Image] = field(default_factory=list)
    _tb_images: List[Image.Image] = field(default_factory=list)
    _tb_split_xs: List[int] = field(default_factory=list)


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


def process_view(
    view_img: Image.Image,
    slug: str,
    index: int,
    args: argparse.Namespace,
    *,
    do_svg: bool,
    need_regions: bool,
    expected: int,
    total_views: int,
    collectors: Collectors,
) -> None:
    """Emit every artifact for one view (full view, regions, clean, legend, SVG)."""
    flag, info = review(view_img, expected, total_views)
    base = f"{args.prefix}-{slug}"
    pdf_path, png_path = write_artifact_set(view_img, args.outdir, base, args.png)
    collectors.pdf_paths.append(pdf_path)
    if png_path:
        collectors.png_paths.append(png_path)
        print(f"  [{flag}] {os.path.basename(pdf_path)} + {os.path.basename(png_path)}  {info}")
    else:
        print(f"  [{flag}] {os.path.basename(pdf_path)}  {info}")

    if not need_regions:
        return

    drawing, title_block, debug, region_info = extract_regions_from_view(
        view_img,
        override_x=args.title_block_start_x,
        fallback_ratio=args.title_block_fallback_ratio,
    )

    # 1.7.0: record every title-block height so truncation can be surfaced after the
    # loop, independent of whether --reconstruct-titleblock was passed.
    collectors.tb_heights.append(int(title_block.height))
    collectors.tb_slugs.append(slug)

    # Store in-memory data for the post-loop reconstruction pass.
    if getattr(args, "reconstruct_titleblock", False):
        collectors._view_images.append(view_img)
        collectors._tb_images.append(title_block)
        collectors._tb_split_xs.append(int(region_info.get("x", 0)))

    if args.extract_title_blocks:
        drawing_base = f"{args.prefix}-{slug}-drawing"
        title_base = f"{args.prefix}-{slug}-title-block"
        debug_base = f"{args.prefix}-{slug}-debug"

        drawing_pdf, drawing_png = write_artifact_set(drawing, args.outdir, drawing_base, args.png)
        title_pdf, title_png = write_artifact_set(title_block, args.outdir, title_base, args.png)
        collectors.drawing_paths.append(drawing_pdf)
        collectors.title_block_paths.append(title_pdf)
        if drawing_png:
            collectors.drawing_paths.append(drawing_png)
        if title_png:
            collectors.title_block_paths.append(title_png)

        debug_png = ""
        if args.debug_overlays:
            debug_png = os.path.join(args.outdir, f"{debug_base}.png")
            render_png(debug, debug_png)
            collectors.debug_paths.append(debug_png)

        region_item = {
            "view": slug,
            "view_index": index,
            "title_block_detection": region_info,
            "drawing_files": names(drawing_pdf, drawing_png),
            "title_block_files": names(title_pdf, title_png),
        }
        if getattr(args, "ocr_title_blocks", False):
            from stv.ocr import ocr_title_block

            ocr_info = ocr_title_block(title_block)
            region_item["title_block_ocr"] = ocr_info
            _fields = ocr_info.get("fields") or {}
            _status = (
                "low-res-skip" if "skipped_low_res" in ocr_info
                else "unavailable" if ocr_info.get("engine") is None
                else "error" if "error" in ocr_info
                else "low-res-ocr" if ocr_info.get("low_res_recovered")
                else "ok"
            )
            print(
                f"    [ocr] {slug}: {_status} "
                f"sheet_title={_fields.get('sheet_title')!r} "
                f"sheet_number={_fields.get('sheet_number')!r} scale={_fields.get('scale')!r}"
            )
        if debug_png:
            region_item["debug_overlay"] = os.path.basename(debug_png)

        # 1.8.0 (audit F2): read the top-left banner -> regional variant as data.
        if getattr(args, "ocr_headers", False):
            from stv.ocr import ocr_sheet_header
            from stv.regions import extract_sheet_header

            header_img = extract_sheet_header(view_img, int(region_info.get("x", 0)))
            header_ocr = ocr_sheet_header(header_img)
            header_base = f"{args.prefix}-{slug}-header"
            header_pdf, header_png = write_artifact_set(header_img, args.outdir, header_base, args.png)
            collectors.header_paths.append(header_pdf)
            if header_png:
                collectors.header_paths.append(header_png)
            region_item["sheet_header_ocr"] = header_ocr
            collectors.header_items.append({
                "view": slug,
                "view_index": index,
                "regional_variant": header_ocr.get("regional_variant"),
                "header_text": header_ocr.get("text"),
                "header_files": names(header_pdf, header_png),
            })
            print(
                f"    [header] {slug}: regional_variant={header_ocr.get('regional_variant')!r} "
                f"text={header_ocr.get('text')!r}"
            )

        collectors.region_manifest_items.append(region_item)

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
            per_manifest = {**manifest_base(args.prefix), "view": slug, "items": [region_item]}
            status = write_zip(per_zip, per_members, per_manifest)
            collectors.per_view_zip_paths.append(per_zip)
            print(f"    [zip] {per_zip}  ({len(per_members)} files, integrity {status})")

    # Legend extraction runs on the drawing region; its bbox also masks the footer pass.
    legend_box: Optional[Box] = None
    if args.extract_legend:
        legend_img, legend_box, legend_info = extract_legend_from_drawing(drawing)
        if legend_img is not None:
            legend_base = f"{args.prefix}-{slug}-legend"
            legend_pdf, legend_png = write_artifact_set(legend_img, args.outdir, legend_base, args.png)
            collectors.legend_paths.append(legend_pdf)
            if legend_png:
                collectors.legend_paths.append(legend_png)
            legend_item = {
                "view": slug,
                "view_index": index,
                "legend_detection": legend_info,
                "legend_files": names(legend_pdf, legend_png),
            }
            # 1.7.0: optionally itemize the key box into a structured BOM so the
            # parts list is emitted as data (an audit found it being mis-read by eye).
            if getattr(args, "ocr_legend", False):
                from stv.ocr import ocr_legend

                bom = ocr_legend(legend_img)
                legend_item["legend_bom"] = bom
                collectors.legend_bom_items.append({"view": slug, "bom": bom})
                items = bom.get("items") or []
                summary = "; ".join(
                    (it.get("label") or "?") + " " + ", ".join(
                        (f"{e.get('descriptor')} " if e.get("descriptor") else "") + f"x{e.get('qty')}"
                        for e in (it.get("entries") or [])
                    ).strip()
                    for it in items
                ) if items else bom.get("skipped_low_res") or bom.get("skipped") or "no items parsed"
                print(f"    [legend-bom] {slug}: {summary}")
            collectors.legend_manifest_items.append(legend_item)
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
        collectors.clean_paths.append(clean_pdf)
        if clean_png:
            collectors.clean_paths.append(clean_png)
        collectors.clean_manifest_items.append({
            "view": slug,
            "view_index": index,
            "header_footer_removed": clean_info,
            "legend_masked": bool(legend_box),
            "clean_files": names(clean_pdf, clean_png),
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
            collectors.svg_paths.append(svg_master_path)
            layer_files = []
            if args.svg_layers:
                for layer_name, layer_text in layer_svgs.items():
                    layer_path = write_svg(layer_text, args.outdir, f"{args.prefix}-{slug}-{layer_name}")
                    collectors.svg_paths.append(layer_path)
                    layer_files.append(os.path.basename(layer_path))
            collectors.svg_manifest_items.append({
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


def _print_summary(args: argparse.Namespace, c: Collectors, zips: dict) -> None:
    """Print the SUMMARY block in the exact original order and labeling."""
    print("\n=== SUMMARY ===")
    for path in c.pdf_paths:
        print(f"PDF: {path}")
    for path in c.png_paths:
        print(f"PNG: {path}")
    if zips.get("views"):
        print(f"ZIP: {zips['views']}")
    for path in c.drawing_paths:
        print(f"{ext_label(path)}: {path}")
    for path in c.title_block_paths:
        print(f"{ext_label(path)}: {path}")
    for path in c.debug_paths:
        print(f"PNG: {path}")
    for path in c.clean_paths:
        print(f"{ext_label(path)}: {path}")
    for path in c.legend_paths:
        print(f"{ext_label(path)}: {path}")
    for path in c.header_paths:
        print(f"{ext_label(path)}: {path}")
    for path in c.svg_paths:
        print(f"SVG: {path}")
    if zips.get("drawings"):
        print(f"ZIP: {zips['drawings']}")
    if zips.get("title_blocks"):
        print(f"ZIP: {zips['title_blocks']}")
    if zips.get("debug"):
        print(f"ZIP: {zips['debug']}")
    if zips.get("clean"):
        print(f"ZIP: {zips['clean']}")
    if zips.get("legends"):
        print(f"ZIP: {zips['legends']}")
    if zips.get("headers"):
        print(f"ZIP: {zips['headers']}")
    if zips.get("svg"):
        print(f"ZIP: {zips['svg']}")
    for path in c.recon_paths:
        print(f"{ext_label(path)}: {path}")
    if zips.get("recon"):
        print(f"ZIP: {zips['recon']}")
    for path in c.per_view_zip_paths:
        print(f"ZIP: {path}")
    if c.run_manifest_path:
        print(f"JSON: {c.run_manifest_path}")


def _detect_truncation(heights: List[int], slugs: List[str]) -> dict:
    """Flag title blocks shorter than the run maximum (screenshot crops)."""
    from stv.config import TRUNCATION_CUT_FRAC

    if not heights:
        return {"max_px": 0, "cut_views": [], "cut_frac": TRUNCATION_CUT_FRAC}
    mx = max(heights)
    cut = [
        {"view": s, "tb_height": int(h), "missing_px": int(mx - h)}
        for h, s in zip(heights, slugs)
        if h < TRUNCATION_CUT_FRAC * mx
    ]
    return {"max_px": int(mx), "cut_views": cut, "cut_frac": TRUNCATION_CUT_FRAC}


def _write_run_manifest(
    args: argparse.Namespace,
    c: "Collectors",
    zips: dict,
    truncation: dict,
    recon_infos: List[dict],
    views_detected: int,
    requested_unavailable: Optional[dict] = None,
) -> str:
    """Write a single authoritative run manifest with exact counts + provenance.

    Added in 1.7.0 so downstream consumers read counts and per-field provenance as
    data instead of tallying artifacts by hand (an audit found hand-tallies that
    disagreed with the actual outputs).
    """
    import glob
    import json

    def n(pat: str) -> int:
        return len(glob.glob(os.path.join(args.outdir, f"{args.prefix}{pat}")))

    cut_slugs = {cv["view"] for cv in truncation["cut_views"]}
    ocr_status = {}
    ocr_recovered = set()
    for item in c.region_manifest_items:
        ocr = item.get("title_block_ocr")
        if ocr is not None:
            ocr_status[item["view"]] = (
                "low-res-skip" if "skipped_low_res" in ocr
                else "unavailable" if ocr.get("engine") is None
                else "error" if "error" in ocr
                else "low-res-ocr" if ocr.get("low_res_recovered")
                else "ok"
            )
            if ocr.get("low_res_recovered") or (ocr.get("fields") and "skipped_low_res" not in ocr):
                ocr_recovered.add(item["view"])
    legend_views = [it["view"] for it in c.legend_manifest_items]
    legend_fixtures = [
        (row.get("label") or "").strip()
        for it in c.legend_bom_items
        for row in it.get("bom", {}).get("items", [])
        if (row.get("label") or "").strip()
    ]

    per_view = []
    for slug in c.tb_slugs:
        if slug in cut_slugs:
            scale_prov = "inferred-reconstructed (title block truncated; see reconstruction)"
        elif slug in ocr_recovered:
            scale_prov = "ocr-read-from-title-block-crop (verify against the crop)"
        else:
            scale_prov = ("measured-from-title-block-crop "
                          "(OCR self-skipped; read Scale/Sheet Title from the crop)")
        per_view.append({
            "view": slug,
            "title_block_ocr": ocr_status.get(slug, "not-run"),
            "scale_provenance": scale_prov,
            "legend_present": slug in legend_views,
        })

    manifest = {
        **manifest_base(args.prefix),
        "artifact_type": "run-manifest",
        "views_detected": views_detected,
        "authoritative_counts": {
            "pdf": n("*.pdf"), "png": n("*.png"), "svg": n("*.svg"), "zip": n("*.zip"),
            "json": n("*.json") + 1,
        },
        "counts_note": (
            "Counts are globbed from disk by prefix; do not hand-tally from chat. "
            "As of 1.7.1 json is authoritative too: the glob runs before this "
            "run-manifest is written, so +1 accounts for it (json == zips + 1)."
        ),
        "title_block_ocr": {
            "enabled": bool(getattr(args, "ocr_title_blocks", False)),
            "status_per_view": ocr_status,
            "note": "OCR self-skips on <320px title-block columns; read those fields visually.",
        },
        "legend_inventory": {
            "present_on": legend_views,
            "summary": f"present on {len(legend_views)} of {views_detected} views",
            "bom_per_view": c.legend_bom_items if c.legend_bom_items else "run with --ocr-legend to itemize",
        },
        "regional_variants": (
            {
                "per_view": [
                    {"view": it["view"], "regional_variant": it.get("regional_variant"),
                     "header_text": it.get("header_text")}
                    for it in c.header_items
                ],
                "note": (
                    "Parsed from each view's top-left banner via --ocr-headers. Distinct "
                    "variants in one sheet set (e.g. US vs UK/EU) must not be collapsed to "
                    "one region; verify against the header crop."
                ),
            }
            if c.header_items else "run with --ocr-headers to read each view's regional variant"
        ),
        "requested_but_unavailable": (
            requested_unavailable or {
                "_note": "No requested optional outputs were unavailable in this run."
            }
        ),
        "subject_from_legend": {
            "note": (
                "Identify the sheet's domain from these legend entries, not the "
                "drawing silhouette. A recurring reporting error is labeling a "
                "fixtures-in-rows stage plot a 'floor plan' or 'architectural drawing'."
            ),
            "legend_present_on": legend_views,
            "fixtures": legend_fixtures or (
                "legend present; run --ocr-legend to itemize or read the legend crop"
                if legend_views else "no legend detected in any view"
            ),
        },
        "truncation": {
            **truncation,
            "note": "A cut title block's lower rows are absent; reconstructed values are inferred, not read.",
        },
        "reconstruction": {
            "enabled": bool(getattr(args, "reconstruct_titleblock", False)),
            "views": recon_infos,
        },
        "per_view": per_view,
        "provenance_key": {
            "measured": "read from the sheet's own title-block crop or geometry",
            "inferred": "computed/positional reconstruction; verify against the source CAD",
        },
        "model_attribution_caveat": (
            "If a chat transcript stamps a model name, treat it as an unverified label. "
            "This manifest is produced by the tool, not by any model self-report."
        ),
    }
    path = os.path.join(args.outdir, f"{args.prefix}-run-manifest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def run(args: argparse.Namespace) -> None:
    """Run the split-the-views pipeline from parsed arguments."""
    from stv import __built__, __version__

    os.makedirs(args.outdir, exist_ok=True)

    print(f"split-the-views {__version__} ({__built__})")
    print("Filename rules: ascii lowercase, hyphen separators, no spaces/parentheses/underscores")

    # SVG export vectorizes the clean drawing, so it requires header/footer stripping.
    # It also enables legend detection so the legend (sheet chrome) is masked out of the
    # clean drawing before tracing, keeping the clean PDF/PNG and the SVG consistent.
    # requested_but_unavailable: optional outputs the user asked for that the
    # environment cannot produce. 1.8.0 (audit F5): a missing vtracer used to be a
    # console WARN only, so "--svg but 0 SVG" was easy to miss. It is now a tracked,
    # machine-readable gap in the run manifest.
    requested_but_unavailable: dict = {}
    if args.svg:
        args.strip_header_footer = True
        args.extract_legend = True
        if not svg_available():
            requested_but_unavailable["svg"] = (
                "--svg was requested but 'vtracer' is not installed, so 0 SVG files were "
                "produced. Install with: pip install vtracer --break-system-packages"
            )
            print("  [deliverable-gap] --svg requested but 'vtracer' is not installed; "
                  "0 SVG produced (recorded in run manifest under requested_but_unavailable).")
            print("         Install with: pip install vtracer --break-system-packages")

    # Reconstruction requires title blocks; enable extraction if not already set.
    if getattr(args, "reconstruct_titleblock", False):
        args.extract_title_blocks = True

    # OCR runs on the extracted title-block crop; enable extraction if not already set.
    if getattr(args, "ocr_title_blocks", False):
        args.extract_title_blocks = True

    # Header OCR reads the banner left of the title block; it needs the split, so
    # enable title-block extraction (where the split is computed).
    if getattr(args, "ocr_headers", False):
        args.extract_title_blocks = True

    # Legend OCR runs on the extracted legend crop; enable legend extraction.
    if getattr(args, "ocr_legend", False):
        args.extract_legend = True

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

    collectors = Collectors()
    do_svg = args.svg and svg_available()
    need_regions = args.extract_title_blocks or args.strip_header_footer or args.extract_legend

    # Emit full views, preserving v1.2.0 behavior.
    for index, (view_img, slug) in enumerate(zip(view_images, slugs), start=1):
        process_view(
            view_img,
            slug,
            index,
            args,
            do_svg=do_svg,
            need_regions=need_regions,
            expected=expected,
            total_views=len(view_images),
            collectors=collectors,
        )

    # 1.7.0: surface cropped title blocks regardless of --reconstruct-titleblock,
    # so a truncated sheet can never be silently reported as complete (audit finding).
    truncation = _detect_truncation(collectors.tb_heights, collectors.tb_slugs)
    if truncation["cut_views"]:
        print("  [truncation] title block(s) shorter than the run maximum "
              f"({truncation['max_px']}px) -> likely a screenshot crop:")
        for cv in truncation["cut_views"]:
            print(f"    {cv['view']}: title-block {cv['tb_height']}px "
                  f"(missing {cv['missing_px']}px); lower rows (Sheet Title/Number/Scale) are cut")
        if not getattr(args, "reconstruct_titleblock", False):
            print("    -> pass --reconstruct-titleblock to rebuild them "
                  "(reconstructed values are inferred, not read).")

    recon_infos: List[dict] = []
    zips: dict = {}

    if args.zip:
        zip_path = os.path.join(args.outdir, args.zip)
        view_manifest = {
            **manifest_base(args.prefix),
            "artifact_type": "full-views",
            "view_count": len(view_images),
            "files": names(*(collectors.pdf_paths + collectors.png_paths)),
        }
        members = collectors.pdf_paths + collectors.png_paths
        status = write_zip(zip_path, members, view_manifest)
        zips["views"] = zip_path
        print(f"ZIP: {zip_path}  ({len(members)} files, integrity {status})")

    if args.extract_title_blocks:
        region_manifest = {
            **manifest_base(args.prefix),
            "view_count": len(view_images),
            "items": collectors.region_manifest_items,
        }
        drawings_zip = os.path.join(args.outdir, f"{args.prefix}-drawings.zip")
        title_blocks_zip = os.path.join(args.outdir, f"{args.prefix}-title-blocks.zip")
        draw_status = write_zip(drawings_zip, collectors.drawing_paths, {**region_manifest, "artifact_type": "drawings"})
        title_status = write_zip(title_blocks_zip, collectors.title_block_paths, {**region_manifest, "artifact_type": "title-blocks"})
        zips["drawings"] = drawings_zip
        zips["title_blocks"] = title_blocks_zip
        print(f"ZIP: {drawings_zip}  ({len(collectors.drawing_paths)} files, integrity {draw_status})")
        print(f"ZIP: {title_blocks_zip}  ({len(collectors.title_block_paths)} files, integrity {title_status})")
        if collectors.debug_paths:
            debug_zip = os.path.join(args.outdir, f"{args.prefix}-debug-overlays.zip")
            debug_status = write_zip(debug_zip, collectors.debug_paths, {**region_manifest, "artifact_type": "debug-overlays"})
            zips["debug"] = debug_zip
            print(f"ZIP: {debug_zip}  ({len(collectors.debug_paths)} files, integrity {debug_status})")

    if args.strip_header_footer and collectors.clean_paths:
        clean_zip = os.path.join(args.outdir, f"{args.prefix}-clean-drawings.zip")
        clean_manifest = {
            **manifest_base(args.prefix),
            "artifact_type": "clean-drawings",
            "view_count": len(view_images),
            "items": collectors.clean_manifest_items,
        }
        clean_status = write_zip(clean_zip, collectors.clean_paths, clean_manifest)
        zips["clean"] = clean_zip
        print(f"ZIP: {clean_zip}  ({len(collectors.clean_paths)} files, integrity {clean_status})")

    if args.extract_legend and collectors.legend_paths:
        legends_zip = os.path.join(args.outdir, f"{args.prefix}-legends.zip")
        legend_manifest = {
            **manifest_base(args.prefix),
            "artifact_type": "legends",
            "view_count": len(view_images),
            "items": collectors.legend_manifest_items,
        }
        legend_status = write_zip(legends_zip, collectors.legend_paths, legend_manifest)
        zips["legends"] = legends_zip
        print(f"ZIP: {legends_zip}  ({len(collectors.legend_paths)} files, integrity {legend_status})")

    if getattr(args, "ocr_headers", False) and collectors.header_paths:
        headers_zip = os.path.join(args.outdir, f"{args.prefix}-headers.zip")
        headers_manifest = {
            **manifest_base(args.prefix),
            "artifact_type": "headers",
            "view_count": len(view_images),
            "items": collectors.header_items,
        }
        headers_status = write_zip(headers_zip, collectors.header_paths, headers_manifest)
        zips["headers"] = headers_zip
        print(f"ZIP: {headers_zip}  ({len(collectors.header_paths)} files, integrity {headers_status})")

    if do_svg and collectors.svg_paths:
        svg_zip = os.path.join(args.outdir, f"{args.prefix}-clean-svg.zip")
        svg_manifest = {
            **manifest_base(args.prefix),
            "artifact_type": "clean-svg",
            "view_count": len(view_images),
            "items": collectors.svg_manifest_items,
        }
        svg_status = write_zip(svg_zip, collectors.svg_paths, svg_manifest)
        zips["svg"] = svg_zip
        print(f"ZIP: {svg_zip}  ({len(collectors.svg_paths)} files, integrity {svg_status})")

    # -- Reconstruction pass -------------------------------------------------
    # Runs after all views have been processed so every TB crop is available
    # for the height comparison and the reference-view dimension chain lookup.
    if getattr(args, "reconstruct_titleblock", False) and collectors._tb_images:
        recon_sheets, recon_infos = run_reconstruction(
            collectors._view_images,
            collectors._tb_images,
            slugs,
            collectors._tb_split_xs,
            ref_scale_denominator=getattr(args, "reference_scale", 15),
        )
        for slug, sheet_img in recon_sheets.items():
            recon_base = f"{args.prefix}-{slug}-reconstructed"
            recon_pdf, recon_png = write_artifact_set(sheet_img, args.outdir, recon_base, args.png)
            collectors.recon_paths.append(recon_pdf)
            if recon_png:
                collectors.recon_paths.append(recon_png)
            collectors.recon_manifest_items.append({
                "view": slug,
                "artifact_type": "reconstructed-sheet",
                "files": names(recon_pdf, recon_png),
            })

        if collectors.recon_paths:
            recon_zip = os.path.join(args.outdir, f"{args.prefix}-reconstructed.zip")
            recon_manifest = {
                **manifest_base(args.prefix),
                "artifact_type": "reconstructed-sheets",
                "view_count": len(view_images),
                "items": collectors.recon_manifest_items,
            }
            recon_status = write_zip(recon_zip, collectors.recon_paths, recon_manifest)
            zips["recon"] = recon_zip
            print(f"ZIP: {recon_zip}  ({len(collectors.recon_paths)} files, integrity {recon_status})")

    if not getattr(args, "no_run_manifest", False):
        collectors.run_manifest_path = _write_run_manifest(
            args, collectors, zips, truncation, recon_infos, len(view_images),
            requested_unavailable=requested_but_unavailable,
        )
        print(f"JSON: {collectors.run_manifest_path}")

    print("Done.")

    _print_summary(args, collectors, zips)
