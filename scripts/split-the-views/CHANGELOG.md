# Changelog

All notable changes to `split-the-views` are documented here.

## [1.5.0] - 2026-06-25

Feature release: scalable, layer-grouped SVG vectorization of clean drawings.

- Added `--svg` to vectorize each clean drawing into a resolution-independent SVG:
  - `<prefix>-view-XX-clean.svg` (master, scalable, elements grouped by layer)
  - `<prefix>-clean-svg.zip`
- Added `--svg-layers` to also emit each SVG layer as its own standalone scalable file:
  - `<prefix>-view-XX-linework.svg`
  - `<prefix>-view-XX-dimensions.svg`
  - `<prefix>-view-XX-accents.svg`
- Added `--svg-upscale N` to control the pre-trace upscale factor (default 3); higher keeps small text and thin lines legible.
- SVGs are responsive: each carries a `viewBox` plus `width="100%" height="100%"` and `preserveAspectRatio`, so they scale to any container while staying crisp at any zoom.
- Elements are extracted by semantic color layer — `layer-linework` (black geometry), `layer-dimensions` (blue dimension lines/annotation), `layer-accents` (red markers) — with every traced contour an individually addressable `<path id=...>`.
- `--svg` implies `--strip-header-footer` and `--extract-legend`, so the legend (sheet chrome) is masked out of the clean drawing before tracing; the clean PDF/PNG and the SVG stay consistent.
- Vectorization is crop-based and color-separated: each color layer is traced once with a solid-fill polygon trace, so linework stays sharp and the three layers are cleanly separable. Layer fills use fixed CAD-convention colors because antialiased medians wash out at upscale.
- `vtracer` is an optional dependency: when `--svg` is requested without it, the run prints an install hint and skips only the SVG output; all other artifacts are unaffected.
- Additive: existing full-view, drawing/title-block, clean, and legend outputs are byte-for-byte unchanged when `--svg` is not passed. Compatibility wrappers inherit the new flags unchanged.

## [1.4.0] - 2026-06-25

Feature release: clean drawings (header/footer stripping) and legend extraction.

- Added `--strip-header-footer` to emit clean drawings with the top sheet-title band and bottom view-label band removed:
  - `<prefix>-view-XX-clean.pdf/png`
  - `<prefix>-clean-drawings.zip`
- Added `--extract-legend` to auto-detect and crop the gray legend/key box from each drawing:
  - `<prefix>-view-XX-legend.pdf/png`
  - `<prefix>-legends.zip`
- Header/footer stripping is conservative: a band is removed only when it is thin, sits in the outer header/footer zone, and is separated from the drawing body by a clean whitespace gap. It refuses to trim if too much of the crop would be lost, so connected drawing geometry (e.g. a stage deck touching the bottom edge) is preserved.
- Cut edges are extended through faint anti-alias fringe to a genuinely clean row, so no ghost line of the stripped title/label survives the final trim.
- Legend detection uses a solid-fill (integral-image) test that ignores thin antialiased lines, and merges adjacent key-box cells separated by thin white rules into one span. When no qualifying box is found, the view is reported as `no legend detected` and skipped without error.
- When `--strip-header-footer` and `--extract-legend` run together, a detected legend is masked before the footer pass so a corner key-box does not anchor the footer band.
- Both new features are additive: existing `--extract-title-blocks`, full-view, and ZIP outputs are byte-for-byte unchanged when the new flags are not passed. Region extraction is computed automatically when any of `--extract-title-blocks`, `--strip-header-footer`, or `--extract-legend` is set; drawing/title-block files are still emitted only under `--extract-title-blocks`.
- Compatibility wrappers (`split_views.py`, `sheetwright.py`, `extract_regions.py`) inherit the new flags unchanged.

## [1.3.1] - 2026-06-25

Patch release: drawing-region edge artifact cleanup.

- Strips full-span horizontal and vertical edge rule artifacts from extracted drawing-only crops.
- Fixes the missed top horizontal page-break line seen in `view-03-drawing`.
- Adds `drawing_edge_rules_stripped_px` metadata to region manifests for auditability.
- Keeps full-view outputs unchanged; cleanup is applied to extracted drawing regions only.

## [1.3.0] - 2026-06-24

Feature release: drawing/title-block region extraction.

- Added `--extract-title-blocks` to split each view into:
  - `<prefix>-view-XX-drawing.pdf/png`
  - `<prefix>-view-XX-title-block.pdf/png`
- Added two default master extraction bundles:
  - `<prefix>-drawings.zip`
  - `<prefix>-title-blocks.zip`
- Added `manifest.json` inside generated ZIP bundles.
- Added `--debug-overlays` for visual audit of the detected title-block separator line.
- Added `--per-view-zips` for optional per-view packages:
  - `<prefix>-view-XX-regions.zip`
- Added PDF input support through PyMuPDF for existing split-view PDFs.
- Added `--inputs` for treating multiple already-split PDFs/PNGs as separate views.
- Added manual boundary override:
  - `--title-block-start-x <pixels>`
- Added fallback control:
  - `--title-block-fallback-ratio <ratio>`
- Added compatibility wrapper:
  - `scripts/extract_regions.py`

## [1.2.0] - 2026-06-24

Refactor release for Codex / Claude Code skill plugin deployment.

- Restored package/plugin naming to `split-the-views`.
- Release archive naming established as `split-the-views-x.x.x.zip`.
- Primary executable is now `scripts/split_the_views.py`.
- Compatibility wrappers retained:
  - `scripts/split_views.py`
  - `scripts/sheetwright.py`
- Established strict artifact filename rules:
  - lowercase ASCII only;
  - hyphen separators only;
  - no spaces, parentheses, underscores, punctuation, emoji, or unicode;
  - zero-padded view indices: `view-01`, `view-02`, ...
- Added `safe_slug()` sanitization for input stems, prefixes, ZIP names, and user view names.
- Added de-duplication for user-provided view slugs.
- Added optional `--png` export for iOS Photos/mobile-friendly mirrors.
- ZIP bundles now contain the same safe basenames as emitted artifacts.

## [1.1.0] - 2026-06-24

Original one-shot deployment release under `split-the-views`.

- `--input` optional: auto-detects the single image in `/mnt/user-data/uploads/`.
- `--prefix` defaulted to input filename stem.
- ZIP defaulted to `<prefix>-views.zip`.
- Neutral slugs defaulted to `view-1`, `view-2`, ...
