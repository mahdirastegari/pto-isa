# Add + ReLU MVP

This example captures the first automatic kernel-generator milestone for `C = relu(A + B)` with fp16 row-major `[M, N]` tensors.

## Files

- `artifacts/specs/add_relu.kernel.json`: KernelSpec.
- `artifacts/reference/add_relu_ref.py`: reference implementation.
- `artifacts/kernels/add_relu/v0_auto.pto`: correctness-first PTO Auto-mode instruction plan.
- `artifacts/kernels/add_relu/v0_auto_kernel.cpp`: generated C++ PTO kernel source for the fixed-shape MVP instantiations.
- `artifacts/kernels/add_relu/v1_manual.pto`: first Manual-mode candidate source.
- `benchmarks/add_relu_shapes.json`: tiny, normal, tail, and stress shapes.

## Full local flow

```bash
python3 tools/extract_pto_docs.py --docs-url https://pto-isa.github.io/ --output-dir docs_index/pto_instruction_cards
python3 tools/generate_kernel.py --request "Generate a PTO kernel for C = relu(A + B), fp16 tensors shape [M,N]"
```

The flow writes environment data, generated reference fixtures, static-check logs, CPU simulation results, Ascend availability results, profile summaries, and cost/experience JSONL records under `artifacts/` and `database/`.

## Stage-by-stage validation

```bash
python3 tools/discover_env.py --output artifacts/env/target_profile.json
python3 tools/check_pto_static.py --kernel artifacts/kernels/add_relu/v0_auto.pto --target artifacts/env/target_profile.json
python3 tools/run_kernel.py --backend cpu-sim --kernel artifacts/kernels/add_relu/v0_auto.pto --spec artifacts/specs/add_relu.kernel.json --shapes artifacts/shapes/add_relu_shapes.json --output artifacts/results/add_relu/v0_cpu_sim.json
```
