# PTO Generator Agent

Generate a simple correctness-first PTO Auto-mode kernel from a KernelSpec and retrieval bundle.

## Outputs

- `artifacts/kernels/<op_name>/v0_auto.pto`
- `artifacts/kernels/<op_name>/v0_metadata.json`

## Rules

1. Generate simple PTO Auto mode first.
2. Avoid manual double buffering, aggressive tiling, or sync micro-optimization before correctness passes.
3. Preserve tail-handling assumptions in metadata.
4. Use TileLang-Ascend seeds only as inspiration unless a checked conversion path exists.
