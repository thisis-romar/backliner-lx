# Example run - split-the-views 1.5.0

Input: `IMG_0382(1).PNG`, a phone screenshot of a three-view lighting plot.

## Command

```bash
pip install vtracer --break-system-packages -q
python "${CLAUDE_PLUGIN_ROOT}/scripts/split_the_views.py" \
  --png \
  --extract-title-blocks \
  --strip-header-footer \
  --extract-legend \
  --svg \
  --svg-layers \
  --debug-overlays
```

## Expected safe output names (selected)

```text
img-0382-1-view-01.pdf
img-0382-1-view-01.png
img-0382-1-view-01-drawing.pdf
img-0382-1-view-01-title-block.pdf
img-0382-1-view-01-clean.pdf
img-0382-1-view-01-clean.png
img-0382-1-view-01-clean.svg
img-0382-1-view-01-linework.svg
img-0382-1-view-01-dimensions.svg
img-0382-1-view-01-accents.svg
img-0382-1-view-01-legend.pdf
img-0382-1-view-01-debug.png
img-0382-1-view-02-clean.svg
img-0382-1-view-03-clean.svg
img-0382-1-views.zip
img-0382-1-drawings.zip
img-0382-1-title-blocks.zip
img-0382-1-clean-drawings.zip
img-0382-1-legends.zip
img-0382-1-clean-svg.zip
img-0382-1-debug-overlays.zip
```

## SVG behavior on this input

- `--svg` implies `--strip-header-footer` and `--extract-legend`, so view 01's legend is masked out of the clean drawing before tracing; the clean SVG and clean PDF/PNG match.
- Each clean SVG is resolution-independent (`viewBox` + 100% sizing) and groups elements into `layer-linework`, `layer-dimensions`, and `layer-accents`, with every contour an addressable `<path id=...>`.
- Element counts on this sheet: view 01 = 105 (linework 91, dimensions 8, accents 6); view 02 = 82 (linework 3, dimensions 77 — the blue callout text; accents 2); view 03 = 12.
- The source is a raster screenshot, so this is a raster->vector trace. Elements are extracted by color layer, not per object: in the elevations every object touches the common ground line and cannot be separated. For per-fixture geometry and editable dimension text, export SVG directly from the source CAD file.
