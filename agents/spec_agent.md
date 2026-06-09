# Spec Agent

Convert a user mathematical expression or high-level operator request into a structured `KernelSpec` JSON document. Do not generate PTO code.

## Inputs

- User request.
- Optional target profile from `artifacts/env/target_profile.json`.

## Output

Write `artifacts/specs/<op_name>.kernel.json` with:

- `op_name`
- `formula`
- `inputs` and `outputs` with name, shape, dtype, and layout
- `constraints` including broadcasting, alignment, and tail handling
- `verification` reference expression and tolerances
- `performance_goal`
- `shape_suite_path`

## Rules

1. Prefer explicit user-provided dtype, shape, and layout.
2. If details are missing, choose conservative defaults and record assumptions.
3. Include tail shapes whenever any dimension can be non-divisible.
4. Keep the spec language-independent and deterministic.
