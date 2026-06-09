#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Run the automatic kernel-generator MVP end-to-end."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from akg.baseline import generate_reference_outputs, write_reference_module
from akg.generator import (
    generate_auto_kernel,
    generate_manual_kernel,
    profile_result,
    simulate_kernel,
    store_memory,
    write_ascend_result,
)
from akg.pto_docs import load_from_site
from akg.spec import create_kernel_spec, load_shapes, write_shape_suite
from check_pto_static import check_kernel
from discover_env import discover


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_flow(user_request: str, docs_url: str, skip_doc_load: bool = False) -> dict[str, Any]:
    target = discover()
    write_json(Path("artifacts/env/target_profile.json"), target)

    docs_result = {"status": "skipped"}
    if not skip_doc_load:
        docs_result = load_from_site(docs_url, Path("docs_index/pto_instruction_cards"), max_pages=80)
        write_json(Path("artifacts/logs/docs_load.json"), docs_result)

    spec = create_kernel_spec(user_request, Path("artifacts/specs"))
    op_name = spec["op_name"]
    shapes_path = Path(spec["shape_suite_path"])
    write_shape_suite(shapes_path)
    write_shape_suite(Path("benchmarks") / f"{op_name}_shapes.json")
    shapes = load_shapes(shapes_path)

    write_reference_module(spec, Path("artifacts/reference") / f"{op_name}_ref.py")
    reference_manifest = generate_reference_outputs(spec, shapes, Path("artifacts/reference") / op_name)

    kernel_dir = Path("artifacts/kernels") / op_name
    auto_kernel = generate_auto_kernel(spec, kernel_dir)
    static_ok, static_messages = check_kernel(auto_kernel, Path("artifacts/env/target_profile.json"))
    static_log = Path("artifacts/logs") / op_name / "v0_static_check.log"
    static_log.parent.mkdir(parents=True, exist_ok=True)
    static_log.write_text("\n".join(static_messages) + "\n", encoding="utf-8")
    if not static_ok:
        raise RuntimeError("static PTO check failed: " + "; ".join(static_messages))

    result_dir = Path("artifacts/results") / op_name
    cpu_result = simulate_kernel(spec, shapes, result_dir)
    ascend_result = write_ascend_result(result_dir, bool(target.get("npu_available")))

    manual_kernel = generate_manual_kernel(spec, kernel_dir)
    profile = profile_result(spec, cpu_result, Path("artifacts/profiles") / op_name)
    store_memory(spec, profile, cpu_result, ascend_result)

    summary = {
        "op_name": op_name,
        "target": target,
        "docs": docs_result,
        "spec_path": str(Path("artifacts/specs") / f"{op_name}.kernel.json"),
        "shapes_path": str(shapes_path),
        "reference_manifest": reference_manifest,
        "auto_kernel": str(auto_kernel),
        "manual_kernel": str(manual_kernel),
        "static_check": {"status": "pass", "messages": static_messages},
        "cpu_result": cpu_result,
        "ascend_result": ascend_result,
        "profile": profile,
    }
    write_json(Path("artifacts/results") / op_name / "generation_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", default="Generate Ascend PTO kernel for C = relu(A + B), fp16 [M, N].")
    parser.add_argument("--docs-url", default="https://pto-isa.github.io/")
    parser.add_argument("--skip-doc-load", action="store_true")
    args = parser.parse_args()

    summary = run_flow(args.request, args.docs_url, skip_doc_load=args.skip_doc_load)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
