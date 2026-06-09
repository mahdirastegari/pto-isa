# PTO Docs Index

This directory contains agent-readable indexes derived from the PTO ISA manual.

## Instruction cards

`docs_index/pto_instruction_cards/` contains one JSON card per documented PTO instruction used by retrieval and static-check tooling. The card filenames are the instruction spelling without the `pto.` prefix, for example:

- `tadd.json` describes `pto.tadd`.
- `vadd.json` describes `pto.vadd`.
- `set_flag.json` describes `pto.set_flag`.

The committed index contains 283 unique instruction cards. It is generated from `docs/mkdocs/mkdocs.yml`, which is the source nav for the published manual at <https://pto-isa.github.io/>. The generator intentionally excludes documented helper/view pseudo-ops and system scheduling helper pages from the instruction-card count; duplicate spellings such as tile/communication `tgather` are merged into a single card with multiple `sources`.

Regenerate the cards with:

```bash
python3 tools/extract_pto_docs.py --docs-url https://pto-isa.github.io/ --output-dir docs_index/pto_instruction_cards
```
