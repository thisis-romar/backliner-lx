"""Centralized tuning constants and format/path defaults.

Every name here matches the original monolith verbatim so behavior is unchanged;
the only difference is that constants are now grouped by the concern that owns
them, which makes the coupling between thresholds and algorithms explicit.
"""

from __future__ import annotations

from typing import Tuple

# -- environment paths -------------------------------------------------------
UPLOADS_DIR = "/mnt/user-data/uploads"
OUTPUTS_DIR = "/mnt/user-data/outputs"

# -- view detection ----------------------------------------------------------
CLEAN_THRESH = 210       # A row/column has no ink if every pixel is >= this value.
MIN_SEP_H = 4            # Separator bands must be at least this many rows high.
MERGE_GAP = 12           # Nearby separator bands are clustered within this gap.
MIN_VIEW_H = 50          # Ignore short chrome fragments.
EMPTY_INK_PCT = 0.001    # Less than this ink fraction is treated as near-empty.

# -- title-block detection ---------------------------------------------------
TITLE_SEARCH_LEFT = 0.62       # Search starts at 62% of the view width.
TITLE_SEARCH_RIGHT = 0.985     # Ignore the outermost right border.
TITLE_MIN_RATIO = 0.055        # Title block must occupy at least this width.
TITLE_MAX_RATIO = 0.35         # Title block should not occupy more than this width.
TITLE_FALLBACK_RATIO = 0.90    # Used if detection cannot find a strong separator.
TITLE_DARK_THRESH = 185
TITLE_BANDS = 24
TITLE_MIN_BAND_HITS = 8
TITLE_SEPARATOR_PAD = 2        # Pixels removed around the separator line.

# -- edge artifact cleanup for drawing-only crops ----------------------------
EDGE_RULE_DARK_THRESH = 220
EDGE_RULE_COVERAGE = 0.72
EDGE_RULE_SCAN_PX = 12
EDGE_RULE_MAX_STRIP_PX = 8
DRAWING_CROP_PAD = 8

# -- header/footer stripping for clean drawings ------------------------------
HF_INK_THRESH = 180          # Pixel darker than this counts as ink for band detection.
HF_GAP_MIN_PX = 12           # Whitespace gap (rows) that must separate a band from the drawing body.
HF_HEADER_ZONE_FRAC = 0.22   # Header band must begin within this top fraction of the crop.
HF_FOOTER_ZONE_FRAC = 0.22   # Footer band must end within this bottom fraction of the crop.
HF_BAND_MAX_FRAC = 0.16      # A removable band must be thinner than this fraction of crop height...
HF_BAND_MAX_PX = 70          # ...or thinner than this absolute pixel height (whichever is larger).
HF_MIN_KEEP_FRAC = 0.40      # Refuse to strip if it would leave less than this fraction of height.
HF_FRINGE_MAX_PX = 6         # Extend a band cut through this many faint anti-alias rows to a clean edge.
HF_CLEAN_PAD = 12            # Uniform margin around the final clean crop.

# -- legend / key-box extraction (solid gray fill) ---------------------------
LEGEND_GRAY_LO = 208         # Lower bound of the solid gray legend fill value.
LEGEND_GRAY_HI = 248         # Upper bound of the solid gray legend fill value.
LEGEND_CHANNEL_TOL = 14      # Max per-pixel channel spread to count as neutral gray.
LEGEND_SOLID_K = 5           # Window size for the solid-fill test; discards thin antialiased lines.
LEGEND_MERGE_GAP = 30        # Merge solid-gray column/row runs separated by fewer than this many px.
LEGEND_MIN_W_FRAC = 0.16     # Legend bbox must span at least this fraction of crop width.
LEGEND_MIN_H_FRAC = 0.05     # Legend bbox must span at least this fraction of crop height.
LEGEND_MIN_FILL_FRAC = 0.35  # Detected bbox must be at least this gray-filled to qualify.
LEGEND_PAD = 6               # Padding added around the detected legend bbox.

# -- SVG vectorization (clean drawing -> scalable, layer-grouped SVG) ---------
SVG_UPSCALE = 3              # Upscale factor before tracing; more pixels keep text/thin lines legible.
SVG_BG_LUM = 205            # Pixels brighter than this luminance are background and are dropped.
SVG_SAT_MIN = 35            # Min channel spread (max-min) to treat a pixel as chromatic (blue/red).
SVG_COLOR_DELTA = 20        # Dominant-channel lead required to classify a pixel as blue or red.
SVG_MIN_LAYER_PX = 50       # Skip a color layer with fewer than this many pixels.
SVG_FILTER_SPECKLE = 2      # vtracer: drop traced specks smaller than this.
SVG_CORNER_THRESHOLD = 45   # vtracer: corner sharpness; lower keeps technical corners crisp.
SVG_LENGTH_THRESHOLD = 4.0  # vtracer: minimum path segment length.
SVG_PATH_PRECISION = 8      # vtracer: coordinate precision.
# Crisp, fixed layer colors (antialiased medians wash out at upscale; CAD-convention hues).
SVG_LAYERS = (
    ("linework", "black", "#1a1a1a"),
    ("dimensions", "blue", "#3a4fd6"),
    ("accents", "red", "#e22020"),
)

# -- title-block OCR (optional; populates manifest fields from rendered text) -
OCR_UPSCALE = 4             # Upscale the title-block crop before OCR; small rendered text needs it.
OCR_PSM = 6                 # tesseract page-segmentation mode 6 = assume a single uniform block of text.
OCR_MIN_WIDTH_PX = 320      # Heuristic reliability floor: title-block crops narrower than this (e.g. a
                            # 108px phone-screenshot column) are below tesseract's usable resolution, so
                            # OCR self-skips and defers to visual reading. Validate against real hi-res sheets.

# -- output rendering --------------------------------------------------------
PDF_W, PDF_H = 792, 612  # Letter landscape in points.
MAX_IMG_PX = 2400        # Keep ReportLab image embeds below fragile large-image limits.
PNG_MAX_PX = 2400        # Keep PNG exports iOS/mobile friendly.
PDF_INPUT_DPI = 220      # Rasterization density for PDF input pages.

# -- input file extensions ---------------------------------------------------
IMAGE_EXTS = ("*.png", "*.PNG", "*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.webp", "*.WEBP")
PDF_EXTS = ("*.pdf", "*.PDF")
INPUT_EXTS = IMAGE_EXTS + PDF_EXTS

# Shared bounding-box alias: (x0, y0, x1, y1).
Box = Tuple[int, int, int, int]
