# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""KernelSpec parsing and shape-suite helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_SHAPES = {
    "tiny": [[16, 16], [32, 32]],
    "normal": [[1024, 1024], [4096, 4096]],
    "tail": [[1000, 1000], [1025, 2049]],
    "stress": [[8192, 8192]],
}


def normalize_op_name(user_request: str) -> str:
    request = user_request.lower()
    if "relu" in request and "+" in request:
        return "add_relu"
    if "add" in request or "+" in request:
        return "add"
    safe = re.sub(r"[^a-z0-9]+", "_", request).strip("_")[:48]
    return safe or "generated_kernel"


def create_kernel_spec(user_request: str, output_dir: Path) -> dict[str, Any]:
    op_name = normalize_op_name(user_request)
    if op_name not in {"add_relu", "add"}:
        raise ValueError(f"unsupported MVP operator request: {user_request!r}")

    is_relu = op_name == "add_relu"
    spec = {
        "op_name": op_name,
        "formula": "C[i, j] = max(A[i, j] + B[i, j], 0)" if is_relu else "C[i, j] = A[i, j] + B[i, j]",
        "inputs": [
            {"name": "A", "shape": ["M", "N"], "dtype": "fp16", "layout": "row_major"},
            {"name": "B", "shape": ["M", "N"], "dtype": "fp16", "layout": "row_major"},
        ],
        "outputs": [{"name": "C", "shape": ["M", "N"], "dtype": "fp16", "layout": "row_major"}],
        "constraints": {"broadcasting": False, "tail_handling": True, "alignment_required": True},
        "verification": {"reference": "np.maximum(A + B, 0)" if is_relu else "A + B", "rtol": 0.001, "atol": 0.001},
        "performance_goal": {"metric": "latency_us", "baseline": "numpy_cpu_or_torch_npu"},
        "shape_suite_path": f"artifacts/shapes/{op_name}_shapes.json",
        "user_request": user_request,
        "assumptions": ["MVP supports fp16 row-major two-dimensional tensors without broadcasting."],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{op_name}.kernel.json").write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    return spec


def write_shape_suite(path: Path, shapes: dict[str, list[list[int]]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(shapes or DEFAULT_SHAPES, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_shapes(path: Path) -> dict[str, list[list[int]]]:
    return json.loads(path.read_text(encoding="utf-8"))
