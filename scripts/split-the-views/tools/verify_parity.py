#!/usr/bin/env python3
"""Content-aware output parity check between two split-the-views output dirs.

WHY THIS EXISTS
---------------
split-the-views PDFs and ZIPs are NOT byte-stable run-to-run, so `diff` and raw
`sha256` will report false differences. The instability is inherent, not a bug:

  - ReportLab embeds a creation/mod timestamp AND a per-run /FormXob.<32-hex>
    XObject name, the latter living inside a *compressed* stream (so it cannot be
    regex-normalized away).
  - ZIP archives store per-member modification times, and our ZIPs contain those
    same nondeterministic PDFs as members.

Therefore "identical output" must be defined by *content*, not bytes:

  - PNG / SVG / JSON : raw sha256 (these ARE deterministic).
  - PDF              : rasterize every page at 150 DPI and hash the pixels
                       (timestamp- and XObject-name-free).
  - ZIP              : hash each member's content (PDF members rasterized,
                       everything else raw), independent of member mtime.

USAGE
-----
    python tools/verify_parity.py <dir_A> <dir_B>

Exit code 0 == FULL PARITY (every file content-identical). Non-zero otherwise.

Requires PyMuPDF (`pip install pymupdf`).
"""

import hashlib
import sys
import zipfile
from pathlib import Path

import fitz  # PyMuPDF


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pdf_pixhash(data: bytes) -> str:
    """Hash a PDF by its rendered pixels, ignoring timestamps and XObject names."""
    h = hashlib.sha256()
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), alpha=False)
            h.update(f"{pix.width}x{pix.height}:".encode())
            h.update(pix.samples)
    return h.hexdigest()


def member_hash(name: str, data: bytes) -> str:
    return pdf_pixhash(data) if name.lower().endswith(".pdf") else sha(data)


def zip_sig(path: Path):
    with zipfile.ZipFile(path) as z:
        return tuple(
            (i.filename, member_hash(i.filename, z.read(i.filename)))
            for i in sorted(z.infolist(), key=lambda x: x.filename)
        )


def fingerprint(path: Path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return ("pdf", pdf_pixhash(path.read_bytes()))
    if ext == ".zip":
        return ("zip", zip_sig(path))
    return (ext.lstrip("."), sha(path.read_bytes()))


def scan(directory: Path) -> dict:
    return {p.name: fingerprint(p) for p in sorted(directory.iterdir()) if p.is_file()}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    fa, fb = scan(a), scan(b)
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    common = sorted(set(fa) & set(fb))
    mismatch = [n for n in common if fa[n] != fb[n]]

    print(f"A={a} ({len(fa)} files)   B={b} ({len(fb)} files)")
    print(f"only in A: {only_a or '-'}")
    print(f"only in B: {only_b or '-'}")

    by_ext: dict = {}
    for n in common:
        ext = fa[n][0]
        by_ext.setdefault(ext, [0, 0])
        by_ext[ext][0] += 1
        if fa[n] != fb[n]:
            by_ext[ext][1] += 1
    for ext, (total, bad) in sorted(by_ext.items()):
        print(f"  {ext:5s}: {total:2d} compared, {total - bad:2d} identical, {bad} differ")

    if only_a or only_b or mismatch:
        for n in mismatch:
            print("   DIFF", n)
        print("RESULT: NOT IDENTICAL")
        return 1
    print("RESULT: FULL PARITY (all files content-identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
