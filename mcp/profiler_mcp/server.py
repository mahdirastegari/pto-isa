#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""OpenCode MCP server for profiler mcp."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from akg.mcp_stdio import SimpleMcpServer, schema, string_property  # noqa: E402
from akg.mcp_tools import profile  # noqa: E402


def main() -> int:
    tools = {
        "profile": (
            schema(
                "profile",
                "Normalize profile output for a verified kernel",
                {
                    "spec": string_property("KernelSpec JSON path", None),
                    "cpu_result": string_property("CPU result JSON path", None),
                    "output_dir": string_property("Profile output directory", None),
                },
                ["spec", "cpu_result"],
            ),
            profile,
        )
    }
    return SimpleMcpServer("profiler_mcp", tools).serve()


if __name__ == "__main__":
    raise SystemExit(main())
