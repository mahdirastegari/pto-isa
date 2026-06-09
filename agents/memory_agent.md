# Memory Agent

Persist successes, failures, fixes, and measured costs.

## Outputs

- `database/cost_bank/<op_name>.jsonl`
- `database/experience_bank/<op_name>.jsonl`

## Records

Cost records should include target, kernel, version, shape, dtype, tile shape, latency, bandwidth, bottleneck, and correctness. Experience records should include success or failure type, stage, symptom, root cause, fix, and status.
