# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Reference implementation and deterministic test-vector generation."""

from __future__ import annotations

import importlib
import importlib.util
import json
import random
from pathlib import Path
from typing import Any


def numpy_module():
    if importlib.util.find_spec("numpy") is None:
        return None
    return importlib.import_module("numpy")


def reference_scalar(op_name: str, a: float, b: float) -> float:
    summed = a + b
    if op_name == "add_relu":
        return max(summed, 0.0)
    if op_name == "add":
        return summed
    raise ValueError(f"unsupported operator: {op_name}")


def reference_numpy(op_name: str, a: Any, b: Any) -> Any:
    np = numpy_module()
    if np is None:
        return [reference_scalar(op_name, x, y) for x, y in zip(a, b, strict=True)]
    summed = a + b
    if op_name == "add_relu":
        return np.maximum(summed, np.float16(0.0)).astype(np.float16)
    if op_name == "add":
        return summed.astype(np.float16)
    raise ValueError(f"unsupported operator: {op_name}")


def write_reference_module(spec: dict[str, Any], path: Path) -> None:
    op_name = spec["op_name"]
    body = f'''# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Reference implementation for {op_name}."""

from __future__ import annotations

import numpy as np


def reference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    summed = a + b
    return {"np.maximum(summed, np.float16(0.0)).astype(np.float16)" if op_name == "add_relu" else "summed.astype(np.float16)"}
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def generate_reference_outputs(
    spec: dict[str, Any], shapes: dict[str, list[list[int]]], output_dir: Path
) -> dict[str, Any]:
    op_name = spec["op_name"]
    np = numpy_module()
    rng = random.Random(20250609)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for group, group_shapes in shapes.items():
        for shape in group_shapes:
            m, n = shape
            if m * n > 2_500_000:
                cases.append({"group": group, "shape": shape, "status": "skipped_large_fixture"})
                continue
            case_name = f"{group}_{m}x{n}"
            if np is None:
                sample_count = min(m * n, 4096)
                a = [rng.gauss(0.0, 2.0) for _ in range(sample_count)]
                b = [rng.gauss(0.0, 2.0) for _ in range(sample_count)]
                c = reference_numpy(op_name, a, b)
                (output_dir / f"{case_name}_sample.json").write_text(
                    json.dumps({"a": a, "b": b, "expected": c}) + "\n", encoding="utf-8"
                )
            else:
                np_rng = np.random.default_rng(20250609 + m + n)
                a = np_rng.normal(loc=0.0, scale=2.0, size=(m, n)).astype(np.float16)
                b = np_rng.normal(loc=0.0, scale=2.0, size=(m, n)).astype(np.float16)
                c = reference_numpy(op_name, a, b)
                np.save(output_dir / f"{case_name}_a.npy", a)
                np.save(output_dir / f"{case_name}_b.npy", b)
                np.save(output_dir / f"{case_name}_expected.npy", c)
            cases.append({"group": group, "shape": shape, "case": case_name, "status": "written"})
    manifest = {"op_name": op_name, "cases": cases, "fixture_format": "npy" if np is not None else "json_sample"}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
