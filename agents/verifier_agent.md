# Verifier Agent

Validate generated kernels in the required order: static check, CPU simulation, reference comparison, Ascend hardware run, hardware reference comparison.

## Outputs

- `artifacts/logs/<op_name>/<version>_static_check.log`
- `artifacts/results/<op_name>/<version>_cpu_sim.json`
- `artifacts/results/<op_name>/<version>_ascend.json`
- failure classification records for the experience bank

## Failure classes

`static_legality_error`, `compile_error`, `runtime_error`, `wrong_result`, `timeout`, `performance_regression`, `unsupported_target`.
