# Automatic Kernel Generator for Ascend PTO

The automatic kernel generator is an agentic, compiler-like workflow for turning a user operator request into a verified and optimized PTO kernel. It deliberately separates specification, reference generation, simple PTO generation, verification, optimization, profiling, and memory-bank updates so that correctness is established before performance tuning.

## End-to-end flow

```text
User math / operator request
→ KernelSpec
→ Reference implementation
→ PTO Auto kernel
→ CPU simulation
→ Ascend compile and run
→ Correctness verification
→ PTO Manual optimized kernel
→ Profiling
→ Experience + cost database update
```

## Design principles

1. **Correctness first.** The generator must not optimize a kernel until the simple candidate passes static checks, CPU simulation, and hardware verification where hardware is available.
2. **Structured intermediate representation.** Natural language is converted to a `KernelSpec` JSON document before any PTO is written.
3. **Reference-driven verification.** Every generated kernel is compared against a Python, NumPy, PyTorch, or C++ reference implementation over a shape suite with normal and tail cases.
4. **Target-aware generation.** Environment discovery records the available simulator, CANN tools, compiler, runtime, profiler, device, and supported data types before generation.
5. **Repair by classification.** Failures are classified as static legality errors, compile errors, runtime errors, wrong results, timeouts, performance regressions, or unsupported targets before retry.
6. **Persistent memory.** Cost and experience banks store measured profiles, successful schedules, failures, root causes, and fixes for future retrieval.

## Repository integration

This repository provides the PTO implementation and tests. The generator scaffold lives in the following top-level areas:

- `agents/`: OpenCode agent prompts.
- `tools/`: local utility entry points for discovery, static checks, execution orchestration, profiling, comparison, and documentation extraction.
- `mcp/`: MCP server packages for modular tool access.
- `docs_index/`: agent-readable PTO instruction cards, examples, and target profiles.
- `benchmarks/`: reusable shape suites.
- `database/`: JSONL cost and experience banks.
- `artifacts/`: generated specs, references, kernels, logs, results, and profiles.
- `examples/`: worked MVP examples.

## Kernel generation loop

```text
while not solved:
    1. Discover target environment.
    2. Convert the user request to KernelSpec.
    3. Retrieve PTO docs, examples, failures, and cost data.
    4. Generate reference implementation and test data.
    5. Generate a simple PTO Auto-mode candidate.
    6. Run static legality checks.
    7. Compile and execute with CPU simulation.
    8. Compare against reference outputs.
    9. Compile and execute on Ascend hardware when available.
   10. Compare hardware outputs against reference outputs.
   11. Store success or failure experience.
   12. Optimize only after correctness passes.
   13. Profile valid optimized candidates.
   14. Store the best measured cost record and successful strategy.
```

## MVP scope

The initial milestone targets elementwise `C = relu(A + B)` for fp16 row-major `[M, N]` tensors with non-divisible tail shapes. Later milestones should add scalar multiply, reduction, row softmax, matmul, and matmul fusion.

## Implemented MVP entry points

The scaffold now includes executable local adapters for the complete Add+ReLU MVP loop:

```bash
python3 tools/extract_pto_docs.py --docs-url https://pto-isa.github.io/ --output-dir docs_index/pto_instruction_cards
python3 tools/generate_kernel.py --request "Generate a PTO kernel for C = relu(A + B), fp16 tensors shape [M,N]"
```

`tools/generate_kernel.py` performs environment discovery, optional PTO docs loading, KernelSpec creation, shape-suite creation, reference-module generation, deterministic fixture generation, Auto PTO emission, C++ PTO source emission, static checking, CPU-sim/numpy verification, Ascend availability recording, Manual candidate emission, profile normalization, and cost/experience JSONL updates.

The MCP servers under `mcp/` implement an OpenCode-compatible MCP stdio surface with `initialize`, `tools/list`, and `tools/call`. They expose the same local adapters so OpenCode can call environment discovery, PTO docs loading, static checking, CPU simulation, Ascend status recording, profiling, benchmark lookup, and memory-bank append operations.


## Instruction-card coverage

`docs_index/pto_instruction_cards/` contains 283 unique PTO instruction cards generated from the MkDocs navigation that backs <https://pto-isa.github.io/>. Each file is named after the instruction spelling without the `pto.` prefix (for example, `tadd.json` is the card for `pto.tadd`). The companion `manifest.json` records the card count, filtered helper sections, and duplicate source pages merged into a single instruction card.
