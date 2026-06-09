#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Compare generated output arrays with reference arrays."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def numpy_module():
    if importlib.util.find_spec("numpy") is None:
        return None
    return importlib.import_module("numpy")


def load_values(path: Path) -> Any:
    np = numpy_module()
    if path.suffix == ".npy" and np is not None:
        return np.load(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "expected" in data:
        return data["expected"]
    return data


def compare(actual_path: Path, expected_path: Path, rtol: float, atol: float) -> dict[str, Any]:
    np = numpy_module()
    actual = load_values(actual_path)
    expected = load_values(expected_path)
    if np is not None and hasattr(actual, "astype"):
        abs_error = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
        max_error = float(abs_error.max()) if abs_error.size else 0.0
        passed = bool(np.allclose(actual, expected, rtol=rtol, atol=atol))
    else:
        errors = [abs(float(a) - float(e)) for a, e in zip(actual, expected, strict=True)]
        max_error = max(errors) if errors else 0.0
        passed = all(error <= atol + rtol * abs(float(e)) for error, e in zip(errors, expected, strict=True))
    return {"correctness": "pass" if passed else "fail", "max_error": max_error, "rtol": rtol, "atol": atol}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", required=True, help="Path to actual .npy or JSON output")
    parser.add_argument("--expected", required=True, help="Path to expected .npy or JSON output")
    parser.add_argument("--rtol", type=float, default=1e-3)
    parser.add_argument("--atol", type=float, default=1e-3)
    parser.add_argument("--output", help="Optional JSON result path")
    args = parser.parse_args()

    result = compare(Path(args.actual), Path(args.expected), args.rtol, args.atol)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["correctness"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
