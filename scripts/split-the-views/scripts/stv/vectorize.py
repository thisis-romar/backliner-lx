"""Vectorize a clean drawing into a scalable, layer-grouped SVG (optional vtracer)."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image

from stv.config import (
    SVG_BG_LUM,
    SVG_COLOR_DELTA,
    SVG_CORNER_THRESHOLD,
    SVG_FILTER_SPECKLE,
    SVG_LAYERS,
    SVG_LENGTH_THRESHOLD,
    SVG_MIN_LAYER_PX,
    SVG_PATH_PRECISION,
    SVG_SAT_MIN,
    SVG_UPSCALE,
)

try:
    import vtracer  # Raster->vector tracer, used only for --svg.
except Exception:  # pragma: no cover - package remains useful without SVG export.
    vtracer = None


def svg_available() -> bool:
    """Return True when the vtracer backend for --svg is importable."""
    return vtracer is not None


def _svg_color_masks(arr: np.ndarray) -> Dict[str, np.ndarray]:
    """Split an RGB array into linework/dimensions/accents boolean masks.

    Background is dropped by luminance. Chromatic pixels are routed to the blue
    (dimensions) or red (accents) layer by dominant channel; everything else
    that is not background becomes black linework. Antialiased edges fall into
    the nearest layer, which the per-layer trace then smooths.
    """
    red_c = arr[:, :, 0].astype(int)
    green_c = arr[:, :, 1].astype(int)
    blue_c = arr[:, :, 2].astype(int)
    lum = 0.299 * red_c + 0.587 * green_c + 0.114 * blue_c
    spread = np.maximum(np.maximum(red_c, green_c), blue_c) - np.minimum(np.minimum(red_c, green_c), blue_c)

    background = lum > SVG_BG_LUM
    chromatic = (~background) & (spread > SVG_SAT_MIN)
    is_blue = chromatic & (blue_c >= red_c) & (blue_c >= green_c) & ((blue_c - red_c) > SVG_COLOR_DELTA)
    is_red = chromatic & (red_c >= blue_c) & (red_c >= green_c) & ((red_c - blue_c) > SVG_COLOR_DELTA) & ((red_c - green_c) > SVG_COLOR_DELTA)
    is_black = (~background) & (~is_blue) & (~is_red)
    return {"black": is_black, "blue": is_blue, "red": is_red}


def _vtrace_binary_paths(mask: np.ndarray) -> List[str]:
    """Trace a boolean mask with vtracer and return its <path .../> element strings."""
    binary = np.where(mask[:, :, None], 0, 255).astype("uint8").repeat(3, axis=2)
    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "layer.png")
        svg_path = os.path.join(tmp, "layer.svg")
        Image.fromarray(binary).save(png_path)
        vtracer.convert_image_to_svg_py(
            png_path,
            svg_path,
            colormode="binary",
            mode="polygon",
            filter_speckle=SVG_FILTER_SPECKLE,
            corner_threshold=SVG_CORNER_THRESHOLD,
            length_threshold=SVG_LENGTH_THRESHOLD,
            path_precision=SVG_PATH_PRECISION,
        )
        return re.findall(r"<path\b[^>]*/>", Path(svg_path).read_text(encoding="utf-8"))


def _clean_path_element(tag: str, path_id: str) -> str:
    """Strip a path's own fill (group fill applies) and assign a stable id."""
    tag = re.sub(r'\sfill="[^"]*"', "", tag)
    return re.sub(r"^<path", f'<path id="{path_id}"', tag, count=1)


def _svg_header(width: int, height: int) -> str:
    """Return a responsive SVG open tag: viewBox + 100% sizing so it scales to any container."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="100%" preserveAspectRatio="xMidYMid meet">'
    )


def vectorize_to_layered_svg(
    img: Image.Image,
    *,
    upscale: int = SVG_UPSCALE,
) -> Tuple[str, Dict[str, str], Dict[str, object]]:
    """Trace a drawing crop into a scalable, layer-grouped SVG.

    Returns (master_svg, layer_svgs, info):
      - master_svg   : one SVG with linework/dimensions/accents as named <g> groups,
                       every traced contour a separately addressable <path id=...>.
      - layer_svgs   : {layer_name: standalone_svg} for each non-empty layer.
      - info         : per-layer element counts, colors, and the viewBox dimensions.
    The SVG is resolution-independent (viewBox + 100% sizing). Requires vtracer.
    """
    if vtracer is None:
        raise RuntimeError(
            "SVG export requires the 'vtracer' package. Install it with: "
            "pip install vtracer --break-system-packages"
        )

    base = img.convert("RGB")
    width_1x, height_1x = base.size
    width, height = width_1x * upscale, height_1x * upscale
    arr = np.array(base.resize((width, height), Image.LANCZOS))
    masks = _svg_color_masks(arr)
    header = _svg_header(width, height)

    layer_paths: Dict[str, List[str]] = {}
    layer_colors: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for name, key, color in SVG_LAYERS:
        mask = masks[key]
        if int(mask.sum()) < SVG_MIN_LAYER_PX:
            counts[name] = 0
            continue
        raw = _vtrace_binary_paths(mask)
        paths = [_clean_path_element(tag, f"{name}-{i:04d}") for i, tag in enumerate(raw, start=1)]
        layer_paths[name] = paths
        layer_colors[name] = color
        counts[name] = len(paths)

    def group_block(name: str) -> List[str]:
        block = [f'  <g id="layer-{name}" fill="{layer_colors[name]}">']
        block += [f"    {path}" for path in layer_paths[name]]
        block.append("  </g>")
        return block

    master_lines = [header, "  <!-- split-the-views layered scalable export -->"]
    for name, _key, _color in SVG_LAYERS:
        if counts.get(name):
            master_lines += group_block(name)
    master_lines.append("</svg>\n")
    master_svg = "\n".join(master_lines)

    layer_svgs: Dict[str, str] = {}
    for name, _key, _color in SVG_LAYERS:
        if counts.get(name):
            layer_svgs[name] = "\n".join([header, *group_block(name), "</svg>\n"])

    info = {
        "view_box": [0, 0, int(width), int(height)],
        "intrinsic_size_px": [int(width_1x), int(height_1x)],
        "upscale": int(upscale),
        "layer_element_counts": counts,
        "layer_colors": {n: layer_colors.get(n) for n, _k, _c in SVG_LAYERS if counts.get(n)},
        "total_elements": int(sum(counts.values())),
    }
    return master_svg, layer_svgs, info
