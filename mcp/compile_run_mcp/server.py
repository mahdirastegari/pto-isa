#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""OpenCode MCP server for compile run mcp."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from akg.mcp_stdio import SimpleMcpServer, boolean_property, schema, string_property  # noqa: E402
from akg.mcp_tools import generate_full, run_ascend, run_cpu, static_check  # noqa: E402


def main() -> int:
    tools = {
        "static_check": (
            schema(
                "static_check",
                "Run static PTO legality checks before compilation",
                {
                    "kernel": string_property("Generated PTO kernel path", None),
                    "target": string_property("Target profile JSON path", None),
                },
                ["kernel"],
            ),
            static_check,
        ),
        "run_cpu": (
            schema(
                "run_cpu",
                "Run CPU-sim/reference verification over a shape suite",
                {
                    "spec": string_property("KernelSpec JSON path", None),
                    "shapes": string_property("Shape-suite JSON path", None),
                    "output_dir": string_property("Result output directory", None),
                },
                ["spec", "shapes"],
            ),
            run_cpu,
        ),
        "run_ascend": (
            schema(
                "run_ascend",
                "Record or run Ascend backend status when NPU is available",
                {
                    "output_dir": string_property("Result output directory", "artifacts/results/generated"),
                    "npu_available": boolean_property("Whether caller has already detected an NPU", False),
                },
                [],
            ),
            run_ascend,
        ),
        "generate_full": (
            schema(
                "generate_full",
                "Run the full automatic generator flow",
                {
                    "request": string_property(
                        "User math/operator request", "Generate Ascend PTO kernel for C = relu(A + B), fp16 [M,N]."
                    ),
                    "docs_url": string_property("PTO docs root URL", "https://pto-isa.github.io/"),
                    "skip_doc_load": boolean_property("Skip remote docs load for offline runs", False),
                },
                [],
            ),
            generate_full,
        ),
    }
    return SimpleMcpServer("compile_run_mcp", tools).serve()


if __name__ == "__main__":
    raise SystemExit(main())
