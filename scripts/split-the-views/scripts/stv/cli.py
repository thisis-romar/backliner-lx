"""Command-line surface: argument parsing and the main() entrypoint."""

from __future__ import annotations

import argparse

from stv.config import OUTPUTS_DIR, SVG_UPSCALE, TITLE_FALLBACK_RATIO
from stv.pipeline import run


def parse_args(argv=None) -> argparse.Namespace:
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
        "--ocr-title-blocks",
        action="store_true",
        help=(
            "OCR each extracted title block into structured manifest fields "
            "(sheet_title, sheet_number, scale, ...) plus raw text. Implies "
            "--extract-title-blocks. Optional: needs tesseract+pytesseract, and "
            "self-skips on low-resolution (e.g. phone-screenshot) title blocks."
        ),
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
    parser.add_argument(
        "--reconstruct-titleblock",
        action="store_true",
        help=(
            "Detect title blocks shorter than the run maximum (screenshot crops) and reconstruct "
            "the complete sheet: real drawing + real upper TB + computed lower rows with Scale "
            "derived from blue dimension chains. Emits <prefix>-<slug>-reconstructed.pdf/png."
        ),
    )
    parser.add_argument(
        "--reference-scale",
        type=int,
        default=15,
        help=(
            "Scale denominator of the reference (tallest) view, used as the anchor for "
            "dimension-chain scale computation. Default: 15 (i.e. 1:15)."
        ),
    )

    return parser.parse_args(argv)


def main(argv=None) -> None:
    """Parse arguments and run the split-the-views pipeline."""
    run(parse_args(argv))


if __name__ == "__main__":
    main()
