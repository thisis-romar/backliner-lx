"""split-the-views - drawing-sheet artifact toolkit.

The 1.5.0 release refactored the original monolith into a module-per-concern
library with zero behavioral change. Version 1.6.0 added automatic title-block
cut detection and full-sheet reconstruction. Version 1.6.1 added optional
title-block OCR (`--ocr-title-blocks`) and SKILL.md reporting rules that keep
view-label descriptions consistent across models. Version 1.7.0 closes the gaps
an external audit found: structured legend BOM extraction (`--ocr-legend`),
always-on truncation warnings, an authoritative per-run manifest with exact
counts and per-field provenance, reconstruction-provenance tagging plus an
explicit (not silently-defaulted) scale assumption, and a reconstruction
ghost-cell fix. All pre-1.7.0 artifacts remain content-identical for the same
flags; the new behavior is additive and opt-in (the run manifest is an additive
file, suppressible with `--no-run-manifest`).

Module map:
    config      - all tuning thresholds and path/format constants, grouped by concern
    naming      - filename policy (safe slugs, prefixes, zip names, unique view slugs)
    imaging     - shared numpy/PIL primitives (trim, edge-rule strip, runs, solid-fill)
    sources     - input discovery and image/PDF loading
    detect      - view detection, over-split consolidation, view cropping
    regions     - title-block boundary detection, region extraction, debug overlay
    cleaning    - clean-drawing header/footer band stripping
    legend      - gray legend/key-box detection and extraction
    vectorize   - clean-drawing -> scalable, layer-grouped SVG (optional vtracer)
    reconstruct - cut title-block detection and full-sheet reconstruction (1.6.0), provenance (1.7.0)
    ocr         - optional title-block + legend OCR -> structured fields/BOM (optional tesseract)
    review      - per-panel QA flag (ink density, panel-count check)
    render      - PDF/PNG/SVG writers, ZIP bundler, manifest helpers
    pipeline    - input prep, per-view processing, truncation/run-manifest, run() orchestration
    cli         - argparse surface and main() entrypoint
"""

from __future__ import annotations

__version__ = "1.8.0"
__built__ = "2026-06-25"

__all__ = ["__version__", "__built__", "main"]


def main() -> None:
    """Lazily dispatch to the CLI entrypoint (keeps import side effects minimal)."""
    from stv.cli import main as _main

    _main()
