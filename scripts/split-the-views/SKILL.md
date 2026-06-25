---
name: split-the-views
description: >-
  Convert one image of a multi-view drawing sheet into per-view artifacts.
  Version 1.5.1 can extract drawing fields and right-side title blocks, emit
  clean drawings with the sheet-title band and view-label band stripped,
  auto-extract the gray legend/key box, and vectorize clean drawings into
  scalable, layer-grouped SVGs. Use for drawing views,
  plates, sheets, separated views, plan/elevation exports, downloadable per-view
  files, removing the title/header/footer, or extracting the legend from
  CAD/stage-layout sheets.

  Invoke on: "split this drawing", "separate the views", "one PDF per view",
  "give me the plan view by itself", "extract each drawing plate", "remove the
  title block", "extract the title blocks", "remove the title/header/footer",
  "strip the sheet title and the scale label", "give me a clean drawing",
  "extract the legend", "pull out the key box", "convert the views to SVG",
  "vectorize the drawing", "scalable SVG", "separate the drawing from the title
  block", "make the sheets downloadable", or similar drawing-sheet artifact
  requests.

  Do NOT use for: ordinary photographs, single-view images unless the user asks
  for title-block/legend extraction, header/footer stripping, or SVG export, or requests that
  require redrawing/design changes.
---

# split-the-views - Drawing Sheet Artifact Skill

**Version 1.5.1** | 2026-06-25 | package: `split-the-views-1.5.1.zip`

---

## Package naming

Release archives use this SemVer pattern:

```text
split-the-views-x.x.x.zip
```

Current release:

```text
split-the-views-1.5.1.zip
```

The plugin manifest name is:

```text
split-the-views
```

The primary executable is:

```text
scripts/split_the_views.py
```

Compatibility wrappers:

```text
scripts/split_views.py
scripts/sheetwright.py
scripts/extract_regions.py
```

---

## Core vocabulary

```text
view          = one cropped sheet panel, preserved as-is
drawing       = left drawing field after the title block is removed
title-block   = right-side branded/project-info column
clean         = drawing field with the top sheet-title band and bottom view-label band removed
legend        = gray key/legend box cropped out of the drawing field
debug-overlay = PNG review image showing the detected title-block boundary
svg-layer     = linework (black geometry), dimensions (blue), or accents (red) trace layer
```

---

## Invoke rules

1. Run immediately when a user provides a drawing-sheet image and asks for views, plates, sheets, or downloadable per-view outputs.
2. Auto-detect the input only when there is exactly one image/PDF in `/mnt/user-data/uploads/`.
3. Never invent semantic view names. Do not pass `--views plan,side,front` from visual guessing. Omit `--views` unless the user explicitly names the panels.
4. Do not pass `--prefix` unless the user explicitly requests a naming prefix.
5. Use `--png` when the user is on iOS, asks for Photos-compatible files, or had preview/download failures with PDF/ZIP links.
6. Use `--extract-title-blocks` when the user asks to remove/extract/separate title blocks, isolate drawing fields, or separate branded sheet metadata from technical drawing content.
7. Use `--strip-header-footer` when the user asks to remove the sheet title/header, drop the view-label/scale tag at the bottom, or get a "clean" drawing without the surrounding sheet chrome.
8. Use `--extract-legend` when the user asks for the legend, key, or symbol box, or to pull the gray key panel out of a drawing.
9. Use `--svg` (optionally `--svg-layers`) when the user asks to convert/vectorize views or drawings to SVG, wants scalable vector output, or wants drawing elements as selectable paths. Requires the `vtracer` package.
10. Use `--debug-overlays` on the first run of a new drawing style so the title-block boundary can be visually audited.
11. Present every path printed in the `=== SUMMARY ===` block.

---

## Filename rules

All generated filenames must be stable, URL-safe, and iOS-friendly.

**Allowed:**

- lowercase ASCII letters: `a-z`
- digits: `0-9`
- hyphens: `-`
- extensions: `.pdf`, `.png`, `.zip`, `.json` inside ZIP manifests only

**Forbidden:**

- spaces
- parentheses: `(` `)`
- underscores: `_`
- punctuation except the extension dot
- emoji
- non-ASCII/unicode characters
- uppercase letters

**Default full-view naming:**

```text
<input-stem>-view-01.pdf
<input-stem>-view-02.pdf
<input-stem>-view-03.pdf
<input-stem>-views.zip
```

**Extraction naming:**

```text
<input-stem>-view-01-drawing.pdf
<input-stem>-view-01-title-block.pdf
<input-stem>-drawings.zip
<input-stem>-title-blocks.zip
```

**Clean-drawing and legend naming:**

```text
<input-stem>-view-01-clean.pdf
<input-stem>-view-01-legend.pdf
<input-stem>-clean-drawings.zip
<input-stem>-legends.zip
```

**Scalable SVG naming:**

```text
<input-stem>-view-01-clean.svg
<input-stem>-view-01-linework.svg
<input-stem>-view-01-dimensions.svg
<input-stem>-view-01-accents.svg
<input-stem>-clean-svg.zip
```

With `--png`, matching PNG mirrors are added.

Example input:

```text
IMG_0382(1).PNG
```

Generated output with `--png --extract-title-blocks --debug-overlays`:

```text
img-0382-1-view-01.pdf
img-0382-1-view-01.png
img-0382-1-view-01-drawing.pdf
img-0382-1-view-01-drawing.png
img-0382-1-view-01-title-block.pdf
img-0382-1-view-01-title-block.png
img-0382-1-view-01-debug.png
img-0382-1-views.zip
img-0382-1-drawings.zip
img-0382-1-title-blocks.zip
img-0382-1-debug-overlays.zip
```

---

## Minimal invocation

```bash
pip install pillow reportlab numpy pymupdf --break-system-packages -q
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py"
```

---

## iOS-friendly invocation

```bash
pip install pillow reportlab numpy pymupdf --break-system-packages -q
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" --png
```

---

## Extract drawings and title blocks from the original image

```bash
pip install pillow reportlab numpy pymupdf --break-system-packages -q
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --png \
  --extract-title-blocks \
  --debug-overlays
```

Default extraction ZIPs:

```text
<input-stem>-drawings.zip
<input-stem>-title-blocks.zip
```

Optional per-view packages:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --png \
  --extract-title-blocks \
  --debug-overlays \
  --per-view-zips
```

---

## Emit clean drawings and extract the legend

```bash
pip install pillow reportlab numpy pymupdf --break-system-packages -q
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --png \
  --strip-header-footer \
  --extract-legend
```

Clean/legend ZIPs:

```text
<input-stem>-clean-drawings.zip
<input-stem>-legends.zip
```

`--strip-header-footer` removes the top sheet-title band and the bottom view-label/scale band while preserving connected drawing geometry, and automatically masks any detected legend so the clean drawing is legend-free. `--extract-legend` additionally saves that legend as its own cropped artifact and reports `no legend detected` for views without one; without it, a detected legend is masked from the clean drawing and reported as `(masked from clean drawing, not exported)`. The two can be combined with `--extract-title-blocks` in a single run.

---

## Vectorize clean drawings to scalable SVG

```bash
pip install vtracer --break-system-packages -q
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --svg \
  --svg-layers
```

SVG ZIP:

```text
<input-stem>-clean-svg.zip
```

`--svg` traces each clean drawing into a scalable SVG (`viewBox` + 100% sizing) with elements grouped into `layer-linework`, `layer-dimensions`, and `layer-accents`; every contour is an addressable `<path id=...>`. `--svg` implies `--strip-header-footer` and `--extract-legend` so the legend is masked before tracing. `--svg-layers` also emits each layer as a standalone SVG; `--svg-upscale N` tunes trace resolution (default 3). Requires `vtracer`; without it the SVG step is skipped with an install hint and other outputs are unaffected.

Because the source sheets are raster screenshots, this is a true raster→vector trace: elements are extracted by color layer, not per object. In elevations, fixtures/poles touch the common ground line and cannot be separated from a raster — for per-object geometry and editable dimension text, export SVG directly from the source CAD file.

---

## Extract from three existing split PDFs or PNGs

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --inputs view-01.pdf view-02.pdf view-03.pdf \
  --prefix img-0382-1 \
  --png \
  --extract-title-blocks \
  --debug-overlays
```

Each input is treated as one view. PDF inputs are rasterized internally for detection.

---

## Manual title-block override

If the auto-detected title-block boundary is wrong, rerun with a manual x-coordinate from the debug overlay:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --png \
  --extract-title-blocks \
  --title-block-start-x 1041
```

---

## Pipeline

```text
1. LOAD         -> read image/PDF input(s)
2. DETECT       -> find horizontal separator bands for original sheet images
3. SPLIT        -> crop each view as-is
4. EXTRACT      -> optional drawing/title-block extraction
5. CLEAN        -> optional sheet-title/view-label band stripping and legend extraction
6. VECTORIZE    -> optional scalable, layer-grouped SVG tracing of clean drawings
7. REVIEW       -> check panel count, ink density, and detected title-block line
8. OUTPUT       -> safe PDFs, optional PNGs, SVGs, master ZIPs, optional per-view ZIPs
```

No drawing geometry is redrawn. Extraction is crop-based and auditable through debug overlays.


## 1.3.1 crop QA note

Drawing-only crops strip full-span edge rule/page-break artifacts before final trimming. This prevents a horizontal sheet-break line or left border line from becoming the crop boundary while preserving actual drawing geometry.


## 1.4.0 clean/legend QA note

Header/footer stripping is conservative: a band is removed only when it is thin, sits in the outer header/footer zone, and is separated from the drawing body by a clean whitespace gap; it refuses to over-trim. Cut edges are advanced through faint anti-alias fringe so no ghost line of the title/label survives. Legend detection uses a solid-fill test that ignores thin antialiased lines and merges adjacent key-box cells; non-matching views are skipped with `no legend detected`. New outputs are additive — existing full-view and title-block artifacts are unchanged when the new flags are not passed.


## 1.5.0 SVG QA note

SVGs are resolution-independent (`viewBox` + `width="100%" height="100%"` + `preserveAspectRatio`) and verified by rasterizing the output at multiple widths with a constant aspect ratio. Each color layer is traced once (polygon mode, solid-fill) so linework stays sharp and `layer-linework`/`layer-dimensions`/`layer-accents` are cleanly separable, with each contour an addressable `<path id=...>`. Layer fills use fixed CAD-convention colors because antialiased medians wash out at upscale. `vtracer` is optional; when absent, `--svg` is skipped with an install hint and all other artifacts are unaffected. The trace is raster-based and color-grouped, not per-object — per-fixture separation and editable dimension text require the source CAD file.
