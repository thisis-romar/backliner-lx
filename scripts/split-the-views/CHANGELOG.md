# Changelog

All notable changes to `split-the-views` are documented here.

## [1.8.0] - 2026-06-25

Third audit-driven release. A full audit of a 1.7.1 run (the prior chat's
`tourist-rig` output) confirmed the tool's `pdf/png/svg/zip` counts and the
view/truncation detection were correct, but found that the *reporting layer*
left recoverable information on the table and that one optional-output gap was
too quiet. This release implements code-side fixes for what the tool can own,
and sharpens the data it hands the consuming model for what it cannot.

Additive and mostly opt-in; the one behavior change to an existing flag
(`--ocr-legend` produces cleaner labels) is a strict quality improvement and is
called out below.

### Added
- **`--ocr-headers` (audit F2).** Reads each view's top-left banner
  ("TOURIST US 2026 - SMALL RIG" vs "TOURIST UK/EU 2026 - SMALL RIG") into a
  `regional_variant` field on the regions manifest and a new `regional_variants`
  block in the run manifest, and emits the header crops as a
  `<prefix>-headers.zip` bundle. The prior run collapsed a two-region sheet set
  ("US" + "UK/EU") into one region because this banner was never captured;
  it is now machine-readable. New: `extract_sheet_header` (regions),
  `ocr_sheet_header` (ocr), `HEADER_*` constants (config). Best-effort OCR.
- **`requested_but_unavailable` in the run manifest (audit F5).** Optional
  outputs the user asked for but the environment could not produce (today:
  `--svg` with no `vtracer`) are now a tracked, machine-readable field, and the
  console prints `[deliverable-gap]` instead of a generic `[WARN]`. "Asked for
  SVG, got zero SVG" can no longer pass unnoticed.

### Changed
- **Legend label OCR is cleaner (audit F3).** `_text_band` now locates the
  icon/label boundary as the single largest run of near-empty rows in the cell
  (the icon/label gutter) rather than a fixed lower fraction, so icon-edge
  fragments no longer leak into the label. "Jli Doughty Tank Trap" ->
  "Doughty Tank Trap"; all multi-line labels survive intact. Quantities are
  unchanged (they were already correct). Residual single-character glyph noise
  in tiny rendered names (e.g. "Por" for "Par") remains possible and is still
  flagged by the existing "verify against the legend crop" note.
- **Title-block OCR below the resolution floor now attempts recovery before
  skipping (audit F1).** Instead of a blanket skip under `OCR_MIN_WIDTH_PX`, the
  tool runs an aggressive-upscale OCR pass (`OCR_LOWRES_UPSCALE`) and keeps the
  fields if any parse, tagging them `low_res_recovered` /
  `fields_provenance: ocr-low-res-recovered`. It falls back to the skip record
  only when nothing parses. NOTE: this helps borderline crops in the
  ~150-320px band; it does NOT and cannot recover a ~108px phone-screenshot
  column, where character strokes are ~5px and below tesseract's floor. For
  those, the tool still emits `visual-read-required` and the consuming model
  must read the crop. F1 was, at root, a consuming-layer reading failure, not a
  tool defect; this change closes the part the tool can own.

### Refactored
- Introduced `_run_tesseract(img, upscale, psm)` as the single grayscale +
  Lanczos-upscale + tesseract chokepoint; the title-block, legend-cell, and
  header OCR paths now share it instead of repeating the upscale dance.
- `scale_provenance` in the run manifest now reflects whether OCR actually
  recovered fields for a view, rather than always asserting a skip.

## [1.7.1] - 2026-06-25

Second audit-driven patch. A multi-model audit of 1.7.0 runs confirmed the tool's
`pdf/png/svg/zip` counts were correct everywhere, but surfaced two recurring
reporting failures that the tool can prevent at the source:

- **JSON is now an authoritative count.** `run-manifest.json` `authoritative_counts`
  gains a `json` key (globbed from disk, `+1` for the run-manifest itself, so it
  equals `zips + 1`). Previously JSON was the only artifact type the tool did not
  count, so every model hand-tallied it and several got it wrong (one reported
  `json: 1`; another claimed 9, listed 10, with 11 on disk). The number is now in
  the manifest; do not hand-tally it.
- **Legend-anchored subject guard.** New additive `subject_from_legend` block lists
  the legend's fixture labels and instructs readers to name the sheet's domain from
  them, not the drawing silhouette. This targets the most severe audit miss — a
  model labeling a fixtures-in-rows stage-lighting plot a "floor plan / architectural
  drawing." When no legend exists the field says so neutrally.

Both changes are additive manifest fields plus the expected `version`/`package`
bump. For the same flags, all 1.7.0 `pdf/png/svg` artifacts are byte-for-content
identical (verified with `tools/verify_parity.py`); only the JSON manifests differ,
and only by the two new fields and the version strings.

## [1.7.0] - 2026-06-25

Audit-driven hardening. An external audit of a 1.6.1 run found that the tool
itself passed, but that reporting around it failed in three specific ways: the
legend bill-of-materials was read by eye and mis-counted, a cropped title block
could be reported as a complete sheet, and artifact counts were hand-tallied
inconsistently. This release moves each of those facts into tool output as data.
Additive and opt-in: for the same flags, all pre-1.7.0 artifacts are
content-identical (verified — identical file set and byte-identical PNG mirrors;
PDFs differ only by their embedded timestamp). The run manifest is an additive
file, suppressible with `--no-run-manifest`.

- Added `--ocr-legend`: itemizes the extracted legend/key box into structured
  `{label, entries:[{descriptor, qty}]}` rows, written under `legend_bom` in the
  legends manifest and in the run manifest, with a `[legend-bom]` stdout line.
  Implies `--extract-legend`. Unlike the ~108px title-block column, the legend
  crop is wide enough for per-cell OCR: the itemizer splits the box on its
  full-height divider rules, OCRs each cell's lower text band, and parses
  quantities directly. Best-effort (needs tesseract) and degrades to a skip
  record; quantities read reliably, label text may carry minor glyph noise, so a
  "verify against the legend crop" note travels with the data.
- Added `ocr_legend()` plus helpers to `stv/ocr.py`, and config constants
  `LEGEND_OCR_MIN_WIDTH_PX`, `LEGEND_OCR_CELL_MIN_W_PX`, `LEGEND_OCR_UPSCALE`,
  `LEGEND_OCR_PSM`, `LEGEND_DIVIDER_DARK_FRAC`, `LEGEND_TEXT_BAND_FRAC`.
- Always-on truncation warning: title-block heights are recorded on every run and
  any block shorter than `TRUNCATION_CUT_FRAC` x (run max) prints a `[truncation]`
  warning and is recorded in the run manifest — independent of
  `--reconstruct-titleblock`. A cropped sheet can no longer be silently reported
  as complete.
- Added the authoritative per-run manifest `<prefix>-run-manifest.json` (default
  on; `--no-run-manifest` to suppress): `authoritative_counts` globbed from disk,
  per-view provenance (measured vs inferred), legend inventory, OCR status,
  truncation, and full reconstruction details. Counts come from disk, not a
  hand-tally.
- Reconstruction now records provenance and states its scale assumption instead
  of defaulting silently: `run_reconstruction` returns `(sheets, recon_infos)`;
  each reconstructed field is tagged (`inferred-positional`,
  `derived-from-slug-index`, `computed-matched-spans-anchored-on-reference-scale-flag`);
  the stdout line gains `[INFERRED-not-measured; ref=<view> assumed 1:N]`; and the
  manifest names the `reference_view`, `reference_scale_assumed`, and a
  `scale_source` that explicitly says the scale was NOT read from the cut sheet
  and that `--reference-scale` corrects it. (Auto-reading the reference scale was
  evaluated and rejected: the reference title block is the same ~108px column and
  OCRs to garbage, so an explicit, visible assumption is the honest design.)
- Fixed a reconstruction ghost: a template value (e.g. "PLAN VIEW") whose glyph
  tops sat in the band between the cut line and the declared value-cell top was
  left behind under the new value. The cell is now cleared from the cut line when
  that gap is small (`GHOST_BLEED_PX`).
- Added a `fields_provenance: "visual-read-required"` marker and a `reporting_hint`
  to the title-block OCR low-res-skip record, so a downstream reader is nudged to
  fill Scale / Sheet Title from the crop rather than leaving them null.
- Extended the SKILL.md **Reporting results** rules: read legend quantities as
  data via `--ocr-legend`; take counts from the run manifest, not a hand-tally;
  carry the measured-vs-inferred provenance through; and treat any model
  attribution in a transcript as an unverified label.

## [1.6.1] - 2026-06-25

Optional title-block OCR and cross-model reporting guidance. Additive and opt-in;
all pre-1.6.1 artifacts are content-identical when the new flag is not passed.

- Added `--ocr-title-blocks`: OCRs each extracted title block into structured manifest
  fields (`sheet_title`, `sheet_number`, `scale`, `project_name`, `client`, `venue`,
  `job_number`, `drawn_by`, `project_date`) plus `raw_text_lines`, written under the
  `title_block_ocr` key of each drawings-manifest item. Implies `--extract-title-blocks`.
- Added `stv/ocr.py` (`ocr_available`, `ocr_title_block`) and config constants
  `OCR_UPSCALE`, `OCR_PSM`, `OCR_MIN_WIDTH_PX`.
- OCR is OPTIONAL and degrades gracefully, mirroring the SVG/vtracer pattern: with no
  tesseract/pytesseract it returns an `engine: null` skip; on any failure it returns an
  `error` record; it never raises into the pipeline.
- OCR is RESOLUTION-GATED. Title-block crops narrower than `OCR_MIN_WIDTH_PX` (default
  320px) — typical of phone screenshots, where the title-block column is ~108px wide and
  below tesseract's usable text density — return `skipped_low_res` instead of garbled
  fields, and the SKILL.md reporting rules direct the model to read the crop visually.
  (Empirically, tesseract recovers ~0 useful tokens from the 108px column across upscale
  4–12x, psm 4/6, and binarization; OCR's value is on high-resolution source sheets.)
- Added a SKILL.md **Reporting results** section: derive view labels from the title-block
  text/legend rather than the drawing's visual shape; treat each panel independently
  (one sheet may mix variants); flag truncated title blocks; report optional-region
  absence as neutral inventory ("present on N of M"), not a success rate; distinguish
  measured vs. inferred values. This is the primary, model-tier-independent fix for the
  shape-based mislabeling failure mode.

## [1.6.0] - 2026-06-25

Feature release: automatic title-block cut detection and full-sheet reconstruction.

- Added `--reconstruct-titleblock`: detects views whose title block is shorter than
  the run maximum (a screenshot crop) and reconstructs the complete sheet in five steps:
  1. **detect** — compare TB crop heights; flag any crop < 85 % of the tallest as cut.
  2. **identify** — record which field rows are absent (below the cut y-coordinate).
  3. **compute scale** — find the dominant horizontal blue dimension chain in the target
     and reference views; measure tick-to-tick pixel spans; apply the orthographic
     projection principle (same real-world width → matched spans → same scale). When
     spans differ, the ratio gives a proportional estimate.
  4. **reconstruct TB** — splice the real cut-crop pixels (upper portion) with an edited
     copy of the reference TB (lower portion): Sheet Title inferred from slug/position,
     Sheet Number from slug index, Scale from step 3. Unchanged fields (Date, Drawn By)
     are taken verbatim from the reference template.
  5. **composite sheet** — paste the full-height reconstructed TB into the correct column,
     extend the left sheet border, and close the bottom border.
- Emits `<prefix>-<slug>-reconstructed.pdf/png` for each cut view, and bundles them in
  `<prefix>-reconstructed.zip`.
- Added `--reference-scale N` to set the scale denominator of the reference view (default 15).
- `--reconstruct-titleblock` automatically implies `--extract-title-blocks` (title blocks
  must be extracted for height comparison and template access).
- Reconstruction is additive: all existing artifacts (full views, drawings, title blocks,
  clean drawings, legends, SVGs, per-view ZIPs) are byte-for-byte unchanged.
- Added `stv/reconstruct.py` with `CutInfo` dataclass, `detect_cut_blocks`,
  `_find_blue_chain`, `compute_scale`, `identify_missing_rows`, `_derive_field_overrides`,
  `reconstruct_title_block`, `composite_full_sheet`, and `run_reconstruction`.
- Verified: binary artifacts (PDF by rendered pixels, PNG/SVG by SHA-256) are unchanged
  when `--reconstruct-titleblock` is not passed. Only manifests change (version field).
- This is a minor version bump from 1.5.0 (internal refactor, held) to 1.6.0.

## [Unreleased] - internal refactor (no behavior change)

Structural refactor of the implementation with **zero output change**. The public
runtime version is intentionally held at `1.5.0` so the version string embedded in
every manifest stays stable and output parity is exact and verifiable.

- Split the 1,421-line `scripts/split_the_views.py` monolith into a module-per-concern
  library package, `scripts/stv/` (`config`, `naming`, `imaging`, `sources`, `detect`,
  `regions`, `cleaning`, `legend`, `vectorize`, `review`, `render`, `pipeline`, `cli`).
- `scripts/split_the_views.py` is now a thin launcher that calls `stv.cli.main()`.
- Compatibility entrypoints (`split_views.py`, `sheetwright.py`, `extract_regions.py`)
  now import and call `stv.cli.main()` instead of re-executing the module via
  `runpy.run_path`; `extract_regions.py` still injects `--extract-title-blocks`.
- Collapsed the four duplicated edge-scan closures in `strip_edge_rule_lines` into one
  vectorized kernel over precomputed row/column means.
- Added `manifest_base()` and `names()` helpers to remove ~7x duplicated manifest
  headers and ~8x duplicated file-list constructions; manifests still serialize with
  `sort_keys=True`, so byte output is unchanged.
- Extracted the ~145-line per-view loop body into `pipeline.process_view`, with all
  accumulators moved into a `Collectors` dataclass; `main()`/`run()` is now flat.
- `render_pdf` now stages its image embed through a system temp file with a `finally`
  cleanup, so a render failure can no longer leave a stray `*.tmp.png` in the output
  directory. The temp path never affects PDF bytes.
- Verified: with the full flag set on the reference 3-view sheet, all 61 outputs are
  content-identical to pre-refactor 1.5.0 (PDFs compared by rasterized pixels, ZIPs by
  per-member content, PNG/SVG/JSON by SHA-256), and stdout is byte-identical.

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
