# backliner-lx

Production LX floor package for **Tourist @ Mod Club, 26 Jun 2026**.

Master SVG drawing (3 stacked views) + tooling to render it and extract each view as a separate PDF/PNG.

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
│   └── split/                      ← per-view PDFs, PNGs, and ZIP
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
- `pip install pillow reportlab numpy pymupdf --break-system-packages`

---

## Quick Start

```bash
npm install
pip install pillow reportlab numpy pymupdf --break-system-packages -q
npm run extract
```

Outputs 3 view PDFs + PNGs + a ZIP to `output/split/`.

---

## npm Scripts

| Script | What it does |
|---|---|
| `npm run render` | Render SVG → `output/lx-floor-package.png` at 96 DPI |
| `npm run split` | Split master PNG into 3 per-view PDFs + PNGs → `output/split/` |
| `npm run extract` | Full pipeline: render then split |
| `npm run extract:hd` | Same pipeline at 300 DPI |

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

After `npm run extract`:

```
output/
├── lx-floor-package.png               ← master render (4800×3760 px @ 96 dpi)
└── split/
    ├── lx-floor-package-view-01.pdf   ← Floor Plan
    ├── lx-floor-package-view-01.png
    ├── lx-floor-package-view-02.pdf   ← Front Elevation
    ├── lx-floor-package-view-02.png
    ├── lx-floor-package-view-03.pdf   ← Equipment Schedule
    ├── lx-floor-package-view-03.png
    └── lx-floor-package-views.zip     ← all 6 files bundled
```

All files under `output/` are gitignored — regenerate with `npm run extract`.

---

## Editing the Drawing

1. Open `src/lx-floor-package.svg` in Inkscape or any SVG editor.
2. Fixture symbols are defined in the `<defs>` block at the top: `sym-mh`, `sym-mh-elev`, `sym-strobe`, `sym-strobe-elev`, `sym-par`, `sym-split`.
3. Each view is in its own `<g>` group: `view-1-floor-plan`, `view-2-elevation`, `view-3-schedule`.
4. **Do not place any artwork in the white gap zones** (`y = 900–960` and `y = 1860–1920`) — those rows must stay pure white for the split tool's separator detection.
5. After editing: `npm run extract` to regenerate all view images.

---

## How the Split Works

`scripts/split-the-views/` is the [split-the-views v1.5.1](scripts/split-the-views/SKILL.md) Python plugin. It:

1. Scans the rendered PNG row by row for horizontal bands where all pixels are ≥ 210/255 (white / near-white).
2. Identifies those bands as separator rows between views.
3. Crops each view into its own PDF + PNG.
4. Bundles everything into a ZIP.

The 60 px white gaps in the SVG (`y = 900–960`, `y = 1860–1920`) become the detected separator bands at render time.
