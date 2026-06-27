#!/usr/bin/env bash
#
# build-deliverables.sh — assemble the client deliverables ZIP.
#
# Refreshes output/split/ via `npm run extract`, then stages a curated,
# client-friendly tree (clean PDFs/PNGs front and centre, raw layers in
# source/) and zips it to deliverables/tourist-mod-club-lx-floor-package.zip.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SPLIT="output/split"
STAGE="output/deliverables-stage"
PKG="tourist-trance-tour-2026-small-rig"
STAGE_PKG="$STAGE/$PKG"
DELIV_DIR="deliverables"
ZIP_PATH="$DELIV_DIR/$PKG.zip"
PREFIX="lx-floor-package"

# 1. Refresh the split artifacts from the master SVG.
echo "==> Refreshing artifacts (npm run extract)"
npm run --silent extract

# 2. Reset staging tree.
echo "==> Staging deliverables tree"
rm -rf "$STAGE"
mkdir -p "$STAGE_PKG"/{01-drawings-pdf,02-drawings-png,03-master-sheet}
mkdir -p "$STAGE_PKG"/source/{clean-drawings,svg-layers,title-blocks,legends,debug}

# Map view index -> friendly name.
names=("1-plan-view" "2-side-elevation" "3-front-elevation")
for i in 01 02 03; do
  case "$i" in
    01) name="${names[0]}";;
    02) name="${names[1]}";;
    03) name="${names[2]}";;
  esac

  # Full-view PDF + PNG -> top-level deliverables.
  cp "$SPLIT/$PREFIX-view-$i.pdf" "$STAGE_PKG/01-drawings-pdf/$name.pdf"
  cp "$SPLIT/$PREFIX-view-$i.png" "$STAGE_PKG/02-drawings-png/$name.png"

  # Clean drawings (no header/footer/legend).
  cp "$SPLIT/$PREFIX-view-$i-clean.pdf" "$STAGE_PKG/source/clean-drawings/$name-clean.pdf"
  cp "$SPLIT/$PREFIX-view-$i-clean.png" "$STAGE_PKG/source/clean-drawings/$name-clean.png"

  # SVG layers (master + linework/dimensions/accents where present).
  for layer in clean linework dimensions accents; do
    src="$SPLIT/$PREFIX-view-$i-$layer.svg"
    [ -f "$src" ] && cp "$src" "$STAGE_PKG/source/svg-layers/$name-$layer.svg"
  done

  # Title blocks.
  cp "$SPLIT/$PREFIX-view-$i-title-block.pdf" "$STAGE_PKG/source/title-blocks/$name-title-block.pdf"
  cp "$SPLIT/$PREFIX-view-$i-title-block.png" "$STAGE_PKG/source/title-blocks/$name-title-block.png"

  # Legends (only views that have one).
  for ext in pdf png; do
    src="$SPLIT/$PREFIX-view-$i-legend.$ext"
    [ -f "$src" ] && cp "$src" "$STAGE_PKG/source/legends/$name-legend.$ext"
  done

  # Debug overlays.
  cp "$SPLIT/$PREFIX-view-$i-debug.png" "$STAGE_PKG/source/debug/$name-debug.png"
done

# 3. Master sheet (combined render + editable source SVG).
cp output/$PREFIX.png "$STAGE_PKG/03-master-sheet/$PREFIX.png"
cp src/$PREFIX.svg    "$STAGE_PKG/03-master-sheet/$PREFIX.svg"

# 4. Client cover sheet.
BUILD_DATE="$(date -u +%Y-%m-%d)"
cat > "$STAGE_PKG/README.txt" <<EOF
TOURIST — TRANCE TOUR 2026 · SMALL RIG
Production lighting deliverables · SYNRGY  (projects@synrgy.live)
Client: TOURIST · Venue: VARIOUS · Job No: SN0001
DESIGN INTENT ONLY — field-verify all dimensions before fabrication.
Package built: $BUILD_DATE

------------------------------------------------------------------
CONTENTS
------------------------------------------------------------------
01-drawings-pdf/    Print-ready sheets (open these first):
                      1-plan-view.pdf        (TOURIST US 2026)
                      2-side-elevation.pdf   (TOURIST US 2026)
                      3-front-elevation.pdf  (TOURIST UK/EU 2026)
02-drawings-png/    Screen-preview PNGs of the same three sheets.
03-master-sheet/    Full combined sheet:
                      lx-floor-package.png  (rendered)
                      lx-floor-package.svg  (editable vector master)
source/             Secondary / production assets:
  clean-drawings/     drawings with sheet header/footer/legend removed
  svg-layers/         scalable SVGs split by layer (linework / dimensions / accents)
  title-blocks/       title-block column crops
  legends/            symbol legend crops
  debug/              title-block boundary audit overlays

------------------------------------------------------------------
EQUIPMENT  (per legend)
------------------------------------------------------------------
LIGHTING
  16 EA   LED Par
   6 EA   Ayrton Rivale Profile            (red marker in plan)
   3 EA   Chauvet Color Strike M Strobe
STRUCTURAL
   8 EA   Doughty Tank Trap — 6' (2.4 m) poles on weighted bases
   8 EA   Doughty Tank Trap — 4' (1.2 m) poles on weighted bases
DECKS
  10 EA   4' x 8' decks  (2 rows of 4 horizontal + 2 vertical)

------------------------------------------------------------------
NOTES
------------------------------------------------------------------
Deck layout: two 32'-0" rows (4 x 8' decks each) + two 4'x8' vertical
decks. Gaps between rows and between vertical decks are FIELD VERIFY.
All decks 4' x 8'. Verify all dimensions in field before fabrication.
Scaffold poles (Doughty Tank Trap or similar) on weighted bases.
(c) 2026 SYNRGY. Design intent only — not for construction.
EOF

# 5. Zip it.
echo "==> Writing $ZIP_PATH"
mkdir -p "$DELIV_DIR"
rm -f "$ZIP_PATH"
( cd "$STAGE" && zip -r -q -X "$OLDPWD/$ZIP_PATH" "$PKG" )

echo "==> Done"
unzip -l "$ZIP_PATH"
