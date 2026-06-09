#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Normalize profiler data for a generated kernel candidate."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from akg.generator import profile_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--backend", required=True, choices=["cpu-sim", "ascend"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--cpu-result", help="CPU result JSON. Defaults to sibling v0_cpu_sim.json when available.")
    args = parser.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    default_cpu_result = Path("artifacts/results") / spec["op_name"] / "v0_cpu_sim.json"
    cpu_result_path = Path(args.cpu_result) if args.cpu_result else default_cpu_result
    profiler_available = args.backend == "cpu-sim" or bool(shutil.which("msprof"))
    if profiler_available and cpu_result_path.exists():
        result = profile_result(spec, json.loads(cpu_result_path.read_text(encoding="utf-8")), Path(args.output).parent)
    else:
        result = {
            "kernel_path": args.kernel,
            "spec_path": args.spec,
            "backend": args.backend,
            "profiler_available": profiler_available,
            "status": "missing_cpu_result" if profiler_available else "unsupported_target",
        }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if profiler_available else 1


if __name__ == "__main__":
    raise SystemExit(main())
