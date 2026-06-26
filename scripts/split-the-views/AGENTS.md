# AGENTS.md — guide for agents modifying split-the-views

This file is for agents **changing the code**. For agents **operating the tool**
(when to invoke, which flags to pass), read `SKILL.md` instead. For end-user
usage and the module map, read `README.md`.

Read this before editing anything. The most expensive mistakes here come from not
knowing the parity contract and the screenshot-domain assumptions.

---

## 1. The parity contract (read this first)

**Rule: a change to any module must not alter the output of flags it does not
own. Prove it; do not assume it.**

The catch that wastes the most time: **PDFs and ZIPs are not byte-stable
run-to-run**, so `diff`, `cmp`, and raw `sha256` report false differences. This
is inherent, not a bug:

- ReportLab embeds a timestamp **and** a per-run `/FormXob.<32-hex>` XObject name.
  The XObject name lives inside a **compressed stream**, so you cannot regex it out.
- ZIP archives store per-member modification times, and our ZIPs contain those
  same nondeterministic PDFs as members.

So "identical output" is defined by **content**, never bytes:

| File type | Deterministic? | How to compare |
|---|---|---|
| PNG, SVG, JSON | yes | raw `sha256` |
| PDF | no | rasterize at 150 DPI, hash pixels |
| ZIP | no | hash each member's content (PDFs rasterized) |

**The verifier is bundled and executable:**

```bash
python tools/verify_parity.py <baseline_dir> <new_dir>
# exit 0 == FULL PARITY
```

Standard workflow for any change:

```bash
# 1. Capture a baseline from the CURRENT code, full flag set, on the reference sheet.
python scripts/split_the_views.py --input <ref.png> --outdir /tmp/base \
  --png --extract-title-blocks --strip-header-footer --extract-legend \
  --svg --svg-layers --debug-overlays --per-view-zips
# 2. Make your change.
# 3. Re-run into /tmp/new with the same flags.
# 4. Verify.
python tools/verify_parity.py /tmp/base /tmp/new
```

A behavior-preserving refactor must report **FULL PARITY**. A feature addition
must report parity for every pre-existing artifact and add only new files.

---

## 2. Version bumps change manifests (decide deliberately)

`__version__` lives in `scripts/stv/__init__.py` and is embedded in every ZIP
manifest as the `version` and `package` fields (`manifest_base()` in
`render.py`). Bumping it changes those two JSON fields, which changes the
manifest bytes and therefore the manifest sha256 and the ZIP signatures.

This is the **expected and only** delta from a version bump. After bumping,
`verify_parity.py` will show `json` and `zip` as "differ" while `pdf`, `png`,
`svg` stay identical — confirm the JSON diff is *only* those two fields:

```bash
diff <(unzip -p /tmp/base x-views-manifest.json) <(unzip -p /tmp/new x-views-manifest.json)
# expect only: "version" and "package" lines
```

Hold the version when you want an empty-diff proof (pure refactor). Bump it
(minor for features, patch for fixes) when shipping a real change.

---

## 3. Architecture and dependency direction

One-way dependency graph; do not introduce cycles:

```
config, naming        depend on nothing in the package
imaging               depends on config only
detect, regions,      depend on config + imaging
cleaning, legend,
vectorize, review
reconstruct           depends on numpy/PIL only (self-contained domain logic)
render                depends on config + imaging + stv.__version__
pipeline              composes every stage  ← GOD NODE (imports 11 modules)
cli                   the only entrypoint into pipeline
```

**`pipeline.py` is the god node** — the highest-connectivity module and the
biggest blast radius. Changes there can affect every flag. Touch it last and
re-verify hardest.

Optional third-party backends are isolated to one module each so a missing
dependency degrades exactly one capability:
- `fitz` / PyMuPDF → `sources.py` (PDF input only)
- `vtracer` → `vectorize.py` (`--svg` only)

Keep that isolation. Do not import `fitz` or `vtracer` anywhere else.

---

## 4. Recipe: add a new artifact type

The pipeline has a fixed shape. Follow it exactly so parity stays provable:

1. **Emit per view** — add the logic in `pipeline.process_view`, writing files
   via `render.write_artifact_set` / `write_svg`. Use the `names()` helper for
   manifest file lists and `manifest_base()` for manifest headers.
2. **Accumulate** — add `List[str]` fields to the `Collectors` dataclass; append
   to them in `process_view`. Never use module-level globals.
3. **Bundle** — in `pipeline.run`, after the existing ZIP blocks, build the
   master ZIP with `write_zip(zip_path, paths, {**manifest_base(prefix), ...})`.
   Manifests serialize with `sort_keys=True`, so field *order* never matters;
   only the field *set/values* do.
4. **Summary** — add the paths to `_print_summary` in the correct position.
   The SUMMARY order is part of the contract (`SKILL.md` says "present every
   path printed in the SUMMARY block").
5. **Flag** — add the argparse flag in `cli.py`. If it implies another flag,
   set that in `run()` near the top (see how `--svg` and
   `--reconstruct-titleblock` force their prerequisites).
6. **Gate it** — guard the whole feature behind its flag so existing runs are
   byte-for-byte unchanged. Verify with `tools/verify_parity.py`.

---

## 5. Detection thresholds are domain-tuned (do not loosen casually)

Every constant in `config.py` is tuned to **phone-screenshot CAD sheets** and is
conservative *by design* — the package's promise is "no drawing geometry is
redrawn or lost." Loosening a threshold to fix one sheet can silently corrupt
others.

Reference behavior on the canonical 3-view sheet (`IMG_0382.PNG`), which you
should re-check after any detection change:

- 3 views detected at `(290,1100) (1119,1929) (1949,2556)`
- Title-block split at `split-x=1041`, confidence **high**, on all three views
- Legend detected on view-01 only (`box=[531,640,979,779]`); views 02–03 report
  "no legend detected" (correct — they have none)
- Clean drawings strip header 22px on all, footer 32px on views 01–02
- SVG element counts: view-01=105, view-02=82, view-03=12

If a detection change moves any of these numbers, that is a regression unless you
can justify it. The title block borders are pixel-locked at x=1056/1164 across
all sheets in this set — a useful invariant for sanity checks.

---

## 6. The reconstruction module (`reconstruct.py`)

`--reconstruct-titleblock` encodes five steps; the domain knowledge in this
module is **measured, not guessable**, so be careful editing the constants.

- `TB_CUT_FRAC = 0.85` — a title block shorter than 85% of the run's tallest is
  treated as a screenshot crop.
- `_FIELD_POSITIONS_810` — value-cell bounds `(y0,y1,x0,x1)` in a **108×810**
  title block, measured by scanning the reference TB for first/last ink rows per
  band. These are specific to the SYNRGY template. A different template needs
  re-measurement (scan a complete TB; print ink-row extents per row band).
- `_TEXT_COLOR = (52,48,48)` — sampled from the reference TB value text.
- **Scale computation** (`_find_blue_chain` + `compute_scale`) rests on the
  orthographic projection principle: two views showing the same real-world width
  at the same screenshot zoom have **identical tick-to-tick pixel spans**, hence
  the same scale. On the reference sheet both chains span 645px → ratio 1.0 →
  `matched-spans` → 1:15. When spans differ, the ratio gives a proportional
  estimate (`ratio-computed`). The reference scale denominator defaults to 15
  and is overridable with `--reference-scale`.
- Sheet Title is inferred from the slug keywords first (`_SLUG_TITLE_MAP`), then
  view position (`_POSITION_TITLE_MAP`). Sheet Number comes from trailing slug
  digits. Date and Drawn By are **not** overridden — they are taken verbatim
  from the reference template because they are identical across the sheet set.

Limits to preserve in any edit: the drawing resolution is capped by the source
screenshot (no upscaling adds detail), and reconstructed glyphs use DejaVu Sans
Condensed, not the original CAD font. Values are correct; lettering is a
substitute. State this when presenting reconstructed output.

---

## 7. Quick checklist before you finish

- [ ] `python -m py_compile scripts/stv/*.py scripts/*.py` passes.
- [ ] Imports still acyclic; no `fitz`/`vtracer` outside their owner modules.
- [ ] `tools/verify_parity.py` shows FULL PARITY (refactor) or
      parity-on-existing + new-files-only (feature).
- [ ] If you bumped `__version__`, confirmed the manifest diff is only
      `version` + `package`.
- [ ] New flag gated so default runs are unchanged.
- [ ] Reference-sheet detection numbers (§5) unchanged or justified.
- [ ] `CHANGELOG.md` updated; `SKILL.md` updated if a flag or behavior changed.
- [ ] No `__pycache__` / `*.pyc` left in the tree before zipping.

---

## 8. On knowledge-graph tooling (Graphify et al.)

At the current scale (~14 modules, ~1,900 lines with one-way deps), a knowledge
graph is overhead — this file plus the README architecture section already
capture the structure. Reach for Graphify (`pip install graphifyy`;
`/graphify scripts/stv/`) when the package crosses ~30 modules / ~5,000 lines,
or when an agent must onboard with no session history; it will surface
`pipeline.py` as the god node and draw the import DAG. Note that a graph captures
code *structure* — it cannot encode the domain facts in §5 and §6, which is why
this file exists.
