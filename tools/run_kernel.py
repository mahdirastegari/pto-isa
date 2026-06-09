#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Compile/run a generated kernel candidate through the available local backend adapter."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from akg.generator import simulate_kernel, write_ascend_result
from akg.spec import load_shapes


def backend_available(backend: str) -> bool:
    if backend == "cpu-sim":
        return Path("tests/run_cpu.py").exists()
    if backend == "ascend":
        return bool(shutil.which("npu-smi"))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=["cpu-sim", "ascend"])
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--shapes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    kernel = Path(args.kernel)
    spec_path = Path(args.spec)
    shapes_path = Path(args.shapes)
    missing = [str(path) for path in [kernel, spec_path, shapes_path] if not path.exists()]
    if missing:
        result: dict[str, Any] = {
            "backend": args.backend,
            "compile_status": "missing_input",
            "run_status": "missing_input",
            "correctness": "not_run",
            "failed_shapes": [],
            "max_error": None,
            "missing_inputs": missing,
        }
    elif args.backend == "cpu-sim":
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        result = simulate_kernel(spec, load_shapes(shapes_path), Path(args.output).parent)
    else:
        result = write_ascend_result(Path(args.output).parent, backend_available("ascend"))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("compile_status") in {"success", "pending_hardware_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
