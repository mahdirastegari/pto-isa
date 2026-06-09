# Baseline Agent

Generate a reference implementation and correctness tests from a KernelSpec.

## Outputs

- `artifacts/reference/<op_name>_ref.py`
- `artifacts/tests/<op_name>_test.py`
- expected outputs or checksums when practical

## Test requirements

Include tiny, normal, large, tail, random, zero, negative, and edge-value cases. Prefer PyTorch when the target expression uses PyTorch syntax; otherwise use NumPy.
