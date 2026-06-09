# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Tool handlers shared by the MCP servers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from akg.generator import profile_result, simulate_kernel, write_ascend_result
from akg.pto_docs import load_from_site
from akg.spec import create_kernel_spec, load_shapes, write_shape_suite
from check_pto_static import check_kernel
from discover_env import discover
from generate_kernel import run_flow


def discover_environment(args: dict[str, Any]) -> dict[str, Any]:
    profile = discover()
    output = Path(args.get("output", "artifacts/env/target_profile.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output": str(output), "profile": profile}


def load_pto_docs(args: dict[str, Any]) -> dict[str, Any]:
    return load_from_site(
        args.get("docs_url", "https://pto-isa.github.io/"),
        Path(args.get("output_dir", "docs_index/pto_instruction_cards")),
        int(args.get("max_pages", 80)),
    )


def create_spec(args: dict[str, Any]) -> dict[str, Any]:
    spec = create_kernel_spec(args["request"], Path(args.get("output_dir", "artifacts/specs")))
    write_shape_suite(Path(spec["shape_suite_path"]))
    return spec


def static_check(args: dict[str, Any]) -> dict[str, Any]:
    ok, messages = check_kernel(Path(args["kernel"]), Path(args["target"]) if args.get("target") else None)
    return {"ok": ok, "messages": messages}


def run_cpu(args: dict[str, Any]) -> dict[str, Any]:
    spec = json.loads(Path(args["spec"]).read_text(encoding="utf-8"))
    shapes = load_shapes(Path(args["shapes"]))
    return simulate_kernel(spec, shapes, Path(args.get("output_dir", f"artifacts/results/{spec['op_name']}")))


def run_ascend(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(args.get("output_dir", "artifacts/results/generated"))
    return write_ascend_result(output_dir, bool(args.get("npu_available", False)))


def profile(args: dict[str, Any]) -> dict[str, Any]:
    spec = json.loads(Path(args["spec"]).read_text(encoding="utf-8"))
    cpu_result = json.loads(Path(args["cpu_result"]).read_text(encoding="utf-8"))
    return profile_result(spec, cpu_result, Path(args.get("output_dir", f"artifacts/profiles/{spec['op_name']}")))


def append_record(args: dict[str, Any]) -> dict[str, Any]:
    path = Path(args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(args["record"], sort_keys=True) + "\n")
    return {"path": str(path), "status": "written"}


def list_shapes(args: dict[str, Any]) -> dict[str, Any]:
    path = Path(args.get("path", "benchmarks/add_relu_shapes.json"))
    return {"path": str(path), "shapes": load_shapes(path)}


def generate_full(args: dict[str, Any]) -> dict[str, Any]:
    return run_flow(
        args.get("request", "Generate Ascend PTO kernel for C = relu(A + B), fp16 [M, N]."),
        args.get("docs_url", "https://pto-isa.github.io/"),
        bool(args.get("skip_doc_load", False)),
    )
