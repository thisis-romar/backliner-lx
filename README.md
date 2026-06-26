# backliner-lx

Production LX floor package for **Tourist @ Mod Club, 26 Jun 2026**.

Master SVG drawing (3 stacked views) + tooling to render it and extract each view as a full artifact set: per-view PDFs/PNGs, drawing fields, title blocks, clean drawings (no header/footer/legend), legend crops, and raster-traced layer-separated SVGs.

---

## Project Structure

```
backliner-lx/
├── src/
│   └── lx-floor-package.svg        ← master drawing (3600×2820, 3 views)
├── scripts/
│   ├── render.js                   ← SVG → PNG renderer (sharp / librsvg)
│   └── split-the-views/            ← view-extraction plugin (v1.5.1)
│       └── scripts/split_the_views.py
├── output/                         ← generated files (gitignored)
│   ├── lx-floor-package.png        ← rendered master
│   └── split/                      ← per-view PDFs, PNGs, SVGs, and ZIPs
├── package.json
└── .gitignore
```

---

## The Drawing

Three views stacked vertically with 60 px white separator gaps between them:

```
┌────────────────────────────────────────┬──────────┐
│  VIEW 1: FLOOR PLAN      (y = 0–900)   │ TITLE BK │
├────────────────────────────────────────┴──────────┤
│  (60 px white gap — split-detector row)            │
├────────────────────────────────────────┬──────────┤
│  VIEW 2: FRONT ELEVATION (y = 960–1860)│ TITLE BK │
├────────────────────────────────────────┴──────────┤
│  (60 px white gap — split-detector row)            │
├────────────────────────────────────────┬──────────┤
│  VIEW 3: EQUIPMENT SCHEDULE (y=1920–2820)│ TITLE BK│
└────────────────────────────────────────┴──────────┘
```

| Property | Value |
|---|---|
| Canvas | 3600 × 2820 SVG units |
| Drawing area (per view) | x = 0 – 3160 |
| Title block (per view) | x = 3160 – 3600 (440 px) |
| Scale | 16 px = 1 ft |
| Stage | 40 ft wide × 25 ft deep (640 × 400 px) |

**View 1 — Floor Plan**: top-down layout with MH-1–4 upstage, ST-1–3 mid-stage, 8× PAR64 on decks and DS flanks, Opto Splitter offstage SR, symbol legend, dimension callouts.

**View 2 — Front Elevation**: 7 stands (4× MH, 3× strobe) with 6 ft pipe + 24" base plates, SR and SL deck risers (3 ft), PAR64 on deck tops and DS floor positions, pipe-height dimension annotation.

**View 3 — Equipment Schedule**: gear list table (LIGHTING / STRUCTURAL / SERVICE sections).

---

## Equipment

| Category | Item | Qty |
|---|---|---|
| LIGHTING | Moving Head — Robe Pointe LED 330W Hybrid (clone) | 4 |
| LIGHTING | Tilt Strobe — 8×8 RGBW (JDC1 Clone) | 3 |
| LIGHTING | 18×10W RGBW PAR64 | 8 |
| LIGHTING | Elation Opto Splitter (5-pin DMX) | 1 |
| STRUCTURAL | 6' Black Threaded Pipe | 8 |
| STRUCTURAL | 24" Threaded Base Plate | 8 |
| STRUCTURAL | 36" Deck Leg Set (4-pack) | 2 |
| SERVICE | Transport + Build [City / Truck / 1-Way] | 2 |

---

## Requirements

- **Node.js** ≥ 18
- **Python** 3.8+
- `npm install` (installs `sharp`)
- `pip install pillow reportlab numpy pymupdf vtracer pytesseract --break-system-packages`
- `apt-get install -y tesseract-ocr` (system package — required for `--ocr-title-blocks`)

`vtracer` is required for `--svg` vectorization; without it the SVG step is skipped with an install hint. `tesseract-ocr` + `pytesseract` are required for `--ocr-title-blocks`; without them OCR is skipped gracefully and all other outputs are unaffected.

---

## Quick Start

```bash
npm install
apt-get install -y tesseract-ocr
pip install pillow reportlab numpy pymupdf vtracer pytesseract --break-system-packages -q
npm run extract
```

Outputs the full artifact set to `output/split/` — see [Output Files](#output-files) below.

---

## npm Scripts

| Script | What it does |
|---|---|
| `npm run render` | Render SVG → `output/lx-floor-package.png` at 96 DPI |
| `npm run split` | Full extraction pass on the master PNG → `output/split/` (see below) |
| `npm run extract` | Full pipeline: render then split |
| `npm run extract:hd` | Same pipeline at 300 DPI |

`npm run split` runs the full split-the-views v1.6.1 feature set in one pass:

| Flag | Output produced |
|---|---|
| *(base)* | `*-view-0N.pdf/png` — full view crops |
| `--extract-title-blocks` | `*-view-0N-drawing.pdf/png` + `*-view-0N-title-block.pdf/png` |
| `--ocr-title-blocks` | structured OCR fields in manifests (`sheet_title`, `sheet_number`, `scale`, …) |
| `--strip-header-footer` | `*-view-0N-clean.pdf/png` — no sheet-title band / view-label band / legend |
| `--extract-legend` | `*-view-0N-legend.pdf/png` — symbol legend box (views that have one) |
| `--svg --svg-layers` | `*-view-0N-clean.svg` + layer SVGs (`linework`, `dimensions`, `accents`) |
| `--debug-overlays` | `*-view-0N-debug.png` — title-block boundary audit image |
| `--per-view-zips` | `*-view-0N-regions.zip` — per-view artifact bundle |
| `--reconstruct-titleblock` | `*-view-0N-reconstructed.pdf/png` — full sheet with cut title block rebuilt |

> **SVG note:** `--svg` raster-traces the split PNGs into resolution-independent SVGs grouped by color layer (`layer-linework`, `layer-dimensions`, `layer-accents`). Because the source is already a native SVG, these traced outputs are a secondary format for layer-separated downstream use — they are not a lossless round-trip. For editable geometry, work directly from `src/lx-floor-package.svg`.

---

## `render.js` CLI Flags

```bash
node scripts/render.js [--dpi <n>] [--svg <path>] [--output <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--dpi` | `96` | Render density |
| `--svg` | `src/lx-floor-package.svg` | Source SVG |
| `--output` | `output/lx-floor-package.png` | Output PNG path |

DPI guide: `96` → 4800×3760 px (review), `150` → 7500×5875 px (large format), `300` → 15000×11750 px (print).

---

## Output Files

After `npm run extract` (per-view block repeats for `view-02` and `view-03`):

```
output/
├── lx-floor-package.png                             ← master render (4800×3760 px @ 96 dpi)
└── split/
    ├── lx-floor-package-view-01.pdf                 ← Floor Plan (full view)
    ├── lx-floor-package-view-01.png
    ├── lx-floor-package-view-01-drawing.pdf         ← drawing field (title block removed)
    ├── lx-floor-package-view-01-drawing.png
    ├── lx-floor-package-view-01-title-block.pdf     ← right-side title block column only
    ├── lx-floor-package-view-01-title-block.png
    ├── lx-floor-package-view-01-clean.pdf           ← no header / footer / legend
    ├── lx-floor-package-view-01-clean.png
    ├── lx-floor-package-view-01-clean.svg           ← raster-traced scalable SVG (master)
    ├── lx-floor-package-view-01-linework.svg        ← black geometry layer
    ├── lx-floor-package-view-01-dimensions.svg      ← blue annotation layer
    ├── lx-floor-package-view-01-accents.svg         ← red marker layer
    ├── lx-floor-package-view-01-legend.pdf          ← symbol legend box (view 1 only)
    ├── lx-floor-package-view-01-legend.png
    ├── lx-floor-package-view-01-debug.png           ← title-block boundary audit
    ├── lx-floor-package-view-02.pdf                 ← Front Elevation (same structure)
    ├── …
    ├── lx-floor-package-view-03.pdf                 ← Equipment Schedule (same structure)
    ├── …
    ├── lx-floor-package-views.zip                   ← all full-view PDFs + PNGs
    ├── lx-floor-package-drawings.zip                ← all drawing-field crops
    ├── lx-floor-package-title-blocks.zip            ← all title-block crops
    ├── lx-floor-package-clean-drawings.zip          ← all clean drawings
    ├── lx-floor-package-legends.zip                 ← detected legend crops
    ├── lx-floor-package-clean-svg.zip               ← all SVG files
    └── lx-floor-package-debug-overlays.zip          ← all debug images
```

All files under `output/` are gitignored — regenerate with `npm run extract`.

---

## Editing the Drawing

1. Open `src/lx-floor-package.svg` in Inkscape or any SVG editor.
2. Fixture geometry is inlined directly at each use site as `<g transform="translate(x,y)">` blocks — search for e.g. `<!-- MH-1` to find a specific fixture.
3. Each view is in its own `<g>` group: `view-1-floor-plan`, `view-2-elevation`, `view-3-schedule`.
4. **Do not place any artwork in the white gap zones** (`y = 900–960` and `y = 1860–1920`) — those rows must stay pure white for the split tool's separator detection.
5. After editing: `npm run extract` to regenerate all view images.

---

## How the Split Works

`scripts/split-the-views/` is the [split-the-views v1.5.1](scripts/split-the-views/SKILL.md) Python plugin. Pipeline stages:

1. **Detect** — scans the rendered PNG row by row for horizontal bands where all pixels are ≥ 210/255 (white / near-white). The 60 px white gaps in the SVG (`y = 900–960`, `y = 1860–1920`) become the detected separator bands at render time.
2. **Split** — crops each of the 3 views as-is into full-view PDFs + PNGs.
3. **Extract** — splits each view into a drawing field (left of the vertical title-block divider) and a title-block column (right), stripping full-span edge rule artifacts before trimming.
4. **Clean** — strips the top sheet-title band and bottom view-label/scale band from each drawing field. The symbol legend box is masked out before stripping (and optionally exported as its own crop).
5. **Vectorize** — raster-traces each clean drawing into a scalable SVG (`viewBox` + 100% sizing), separating elements into `layer-linework` (black), `layer-dimensions` (blue), and `layer-accents` (red); every contour is an individually addressable `<path id=…>`.
6. **Output** — emits safe-named PDFs, PNGs, SVGs, and 7 ZIP bundles.
