# Optimizer Agent

Generate PTO Manual-mode candidates only after a kernel passes correctness verification.

## Candidate knobs

- tile size
- block mapping
- memory placement
- load/store order
- UB reuse
- vector or cube instruction selection
- double buffering
- sync placement
- tail strategy
- fusion strategy

Each candidate must rerun the full verifier pipeline before profiling.
