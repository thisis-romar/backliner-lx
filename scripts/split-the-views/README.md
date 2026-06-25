# split-the-views

Codex / Claude Code skill plugin for turning drawing-sheet images into clean downloadable artifacts.

Release package naming is:

```text
split-the-views-x.x.x.zip
```

Current release:

```text
split-the-views-1.5.1.zip
```

## What it does

`split-the-views` detects stacked drawing views in a single image, crops each view as-is, and emits stable downloadable files:

- one PDF per detected view;
- optional PNG mirrors for iOS Photos/mobile preview workflows;
- one ZIP bundle containing the generated view artifacts.

Version `1.3.0` added extraction of drawing fields and right-side title blocks:

- one master ZIP containing all extracted drawing fields;
- one master ZIP containing all extracted title blocks;
- optional debug overlays showing the detected crop boundary;
- optional per-view region ZIPs.

The tool does not redraw, relabel, reinterpret, or design over the source. It only crops and packages.

Version `1.3.1` fixes drawing-region cleanup by stripping full-span edge rule/page-break artifacts from drawing-only crops before final trimming.

Version `1.4.0` adds clean drawings and legend extraction:

- one clean drawing per view with the top sheet-title band and bottom view-label band removed (`--strip-header-footer`);
- one extracted legend/key box per view, auto-detected from its solid gray fill (`--extract-legend`);
- master `<prefix>-clean-drawings.zip` and `<prefix>-legends.zip` bundles.

Both are additive and crop-only: full-view and title-block outputs are unchanged when the new flags are not passed, and nothing is redrawn.


Version `1.5.0` adds scalable, layer-grouped SVG vectorization:

- one scalable SVG per clean drawing, elements grouped by layer (`--svg`);
- optional per-layer standalone SVGs for linework/dimensions/accents (`--svg-layers`);
- master `<prefix>-clean-svg.zip` bundle.

SVGs carry a `viewBox` plus `width="100%"` sizing so they scale to any container, and every traced contour is an individually addressable `<path>`. Requires the optional `vtracer` package.


Version `1.5.1` makes `--strip-header-footer` always produce a legend-free clean drawing:

- legend *detection* is now decoupled from legend *export*. The legend is masked out of the clean drawing whenever `--strip-header-footer` is set, regardless of `--extract-legend`;
- `--extract-legend` now controls only whether the legend is saved as its own file. Without it, a detected legend is masked from the clean drawing and reported as `(masked from clean drawing, not exported)`.

Previously `--strip-header-footer` alone left the legend embedded in the "clean" output. This is the only behavior change; all other outputs are unchanged.


## Terms

```text
view          = one cropped sheet panel, preserved as-is
drawing       = left drawing field after the title block is removed
title-block   = right-side branded/project-info column
clean         = drawing field with the top sheet-title band and bottom view-label band removed
legend        = gray key/legend box cropped out of the drawing field
debug-overlay = PNG review image showing the detected title-block boundary
edge-rule     = full-span border/page-break line touching the outer crop edge
svg-layer     = linework (black geometry), dimensions (blue), or accents (red) trace layer
```

## Filename contract

Generated artifact names must be lowercase ASCII with hyphen separators only.

Allowed:

```text
a-z
0-9
-
.pdf
.png
.zip
```

Forbidden:

```text
spaces
parentheses
underscores
uppercase
punctuation except the extension dot
emoji
unicode / non-ASCII characters
```

Default full-view output pattern:

```text
<input-stem>-view-01.pdf
<input-stem>-view-02.pdf
<input-stem>-view-03.pdf
<input-stem>-views.zip
```

Default extraction output pattern:

```text
<input-stem>-view-01-drawing.pdf
<input-stem>-view-01-title-block.pdf
<input-stem>-drawings.zip
<input-stem>-title-blocks.zip
```

Clean-drawing and legend output pattern:

```text
<input-stem>-view-01-clean.pdf
<input-stem>-view-01-legend.pdf
<input-stem>-clean-drawings.zip
<input-stem>-legends.zip
```

Scalable SVG output pattern:

```text
<input-stem>-view-01-clean.svg
<input-stem>-view-01-linework.svg
<input-stem>-view-01-dimensions.svg
<input-stem>-view-01-accents.svg
<input-stem>-clean-svg.zip
```

Example input:

```text
IMG_0382(1).PNG
```

Generated output with `--png --extract-title-blocks --debug-overlays`:

```text
img-0382-1-view-01.pdf
img-0382-1-view-02.pdf
img-0382-1-view-03.pdf
img-0382-1-view-01.png
img-0382-1-view-02.png
img-0382-1-view-03.png
img-0382-1-view-01-drawing.pdf
img-0382-1-view-01-drawing.png
img-0382-1-view-01-title-block.pdf
img-0382-1-view-01-title-block.png
img-0382-1-view-01-debug.png
img-0382-1-drawings.zip
img-0382-1-title-blocks.zip
img-0382-1-debug-overlays.zip
```

## Quick run

```bash
pip install pillow reportlab numpy pymupdf --break-system-packages -q
python scripts/split_the_views.py --input /path/to/drawing.png --outdir outputs --png
```

## Split views and extract title blocks

```bash
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --png \
  --extract-title-blocks \
  --debug-overlays
```

## Emit clean drawings (strip sheet-title + view-label bands)

```bash
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --png \
  --strip-header-footer
```

This emits one `<input-stem>-view-XX-clean.pdf/png` per view plus `<input-stem>-clean-drawings.zip`. The top sheet-title band and the bottom view-label/scale band are removed; connected drawing geometry (such as a stage deck touching the bottom edge) is preserved. Any detected legend/key box is automatically masked out so the clean drawing is legend-free — add `--extract-legend` to also save that legend as its own file.

## Extract the legend / key box

```bash
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --png \
  --extract-legend
```

This detects the gray legend/key box in each drawing and emits `<input-stem>-view-XX-legend.pdf/png` plus `<input-stem>-legends.zip`. Views without a qualifying box are reported as `no legend detected` and skipped.

## Vectorize clean drawings to scalable SVG

```bash
pip install vtracer --break-system-packages -q
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --svg \
  --svg-layers
```

This emits one scalable `<input-stem>-view-XX-clean.svg` per view plus `<input-stem>-clean-svg.zip`; with `--svg-layers` it also writes `-linework.svg`, `-dimensions.svg`, and `-accents.svg`. `--svg` implies `--strip-header-footer` and `--extract-legend` so the legend is masked out of the clean drawing before tracing. Each SVG scales to any container (viewBox + 100% sizing), and every traced contour is an addressable `<path>` inside a named layer group. Tune trace resolution with `--svg-upscale N` (default 3). Requires `vtracer`; without it the SVG step is skipped and other outputs are unaffected.

Note: the source sheets here are raster screenshots, so this is a true raster→vector trace. Elements are extracted by color layer, not per object — in elevations every object touches the common ground line, so per-fixture separation is not recoverable from a raster. For per-object geometry and editable dimension text, export SVG directly from the source CAD file.

## Everything at once

```bash
pip install vtracer --break-system-packages -q
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --png \
  --extract-title-blocks \
  --strip-header-footer \
  --extract-legend \
  --svg \
  --svg-layers \
  --debug-overlays
```

When clean and legend run together, a detected legend is masked before the footer pass so a corner key-box does not anchor the bottom band.

## Extract regions from already-split PDFs/PNGs

```bash
python scripts/split_the_views.py \
  --inputs view-01.pdf view-02.pdf view-03.pdf \
  --prefix img-0382-1 \
  --outdir outputs \
  --png \
  --extract-title-blocks \
  --debug-overlays
```

## Optional per-view region packages

```bash
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --png \
  --extract-title-blocks \
  --debug-overlays \
  --per-view-zips
```

This emits:

```text
<input-stem>-view-01-regions.zip
<input-stem>-view-02-regions.zip
<input-stem>-view-03-regions.zip
```

## Manual boundary override

If the title-block separator is detected incorrectly, inspect the debug overlay and rerun with:

```bash
python scripts/split_the_views.py \
  --input /path/to/drawing.png \
  --outdir outputs \
  --png \
  --extract-title-blocks \
  --title-block-start-x 1041
```

## Claude/Codex skill invocation

Use this plugin when the user asks for drawing views, plates, sheets, separated views, plan/elevation exports, downloadable per-view files, or title-block extraction from one drawing-sheet image.

Default invocation:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py"
```

iOS/mobile-safe invocation:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" --png
```

Title-block extraction invocation:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" --png --extract-title-blocks --debug-overlays
```

Compatibility entrypoints are also provided:

```bash
python scripts/split_views.py
python scripts/sheetwright.py
python scripts/extract_regions.py
```
