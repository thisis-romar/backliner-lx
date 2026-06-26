"""Filename policy: stable, URL-safe, iOS-friendly artifact names.

Allowed: lowercase ASCII, digits, hyphen, and the extension dot only.
Forbidden: spaces, parentheses, underscores, other punctuation, emoji, unicode,
uppercase. View indices are zero-padded (view-01, view-02, ...).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import List, Sequence


def safe_slug(value: str, *, fallback: str = "artifact", max_len: int = 80) -> str:
    """Return a filesystem-safe slug using the package filename policy."""
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    text = text[:max_len].strip("-")
    return text or fallback


def safe_input_stem(path: str) -> str:
    """Derive a safe default prefix from the input filename stem."""
    return safe_slug(Path(path).stem, fallback="sheet")


def safe_zip_name(prefix: str, zip_arg: str, suffix: str = "views") -> str:
    """Return a safe ZIP filename, preserving only the .zip extension."""
    if not zip_arg:
        return f"{prefix}-{suffix}.zip"
    stem = Path(zip_arg).stem
    return f"{safe_slug(stem, fallback=f'{prefix}-{suffix}')}.zip"


def unique_slugs(raw_slugs: Sequence[str], count: int) -> List[str]:
    """Sanitize and de-duplicate view slugs, then fill missing neutral slugs."""
    width = max(2, len(str(max(count, 1))))
    result: List[str] = []
    seen: Counter[str] = Counter()

    for i in range(count):
        if i < len(raw_slugs) and raw_slugs[i].strip():
            base = safe_slug(raw_slugs[i], fallback=f"view-{i + 1:0{width}d}")
        else:
            base = f"view-{i + 1:0{width}d}"

        seen[base] += 1
        slug = base if seen[base] == 1 else f"{base}-{seen[base]}"
        result.append(slug)

    return result
