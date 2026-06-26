# CLAUDE.md

This project keeps its agent guidance in **[AGENTS.md](./AGENTS.md)** (the
cross-tool convention). Read that file before modifying the code.

Quick pointers:
- **Modifying the code?** → `AGENTS.md` (parity contract, dependency graph,
  extension recipe, domain facts).
- **Operating the tool?** → `SKILL.md` (when to invoke, which flags).
- **Usage / architecture?** → `README.md`.

The one rule that trips up every new agent: **PDF and ZIP outputs are not
byte-stable run-to-run.** Verify changes with `python tools/verify_parity.py
<baseline_dir> <new_dir>`, never with `diff` or raw `sha256`. See AGENTS.md §1.
