#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Discover the local Ascend/PTO target profile for kernel generation."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run_command(args: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip()[:4000],
        "stderr": result.stderr.strip()[:4000],
    }


def detect_cann_version(ascend_home: str | None) -> str | None:
    if not ascend_home:
        return None
    version_files = [
        Path(ascend_home) / "ascend_toolkit_install.info",
        Path(ascend_home) / "latest" / "ascend_toolkit_install.info",
    ]
    for version_file in version_files:
        if not version_file.exists():
            continue
        for line in version_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "version" in line.lower():
                return line.split("=", 1)[-1].strip()
    return None


def discover() -> dict[str, Any]:
    ascend_home = os.environ.get("ASCEND_HOME_PATH") or os.environ.get("ASCEND_TOOLKIT_HOME")
    npu_smi = shutil.which("npu-smi")
    cpu_sim_available = Path("tests/run_cpu.py").exists()
    npu_info = run_command([npu_smi, "info"]) if npu_smi else {"available": False, "error": "npu-smi not found"}

    return {
        "device": "ascend" if npu_info.get("available") else "simulator_or_unknown",
        "host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "cann_version": detect_cann_version(ascend_home),
        "pto_isa_version": None,
        "tilelang_ascend_version": None,
        "compiler_path": shutil.which("bisheng") or shutil.which("clang++") or shutil.which("g++"),
        "runtime_path": ascend_home,
        "profiler_available": bool(shutil.which("msprof")),
        "cpu_sim_available": cpu_sim_available,
        "npu_available": bool(npu_info.get("available")),
        "supported_dtypes": ["fp16", "fp32", "int8", "bf16"],
        "memory": {"GM": None, "UB": None, "L0A": None, "L0B": None, "L0C": None},
        "tools": {"npu_smi": npu_smi, "npu_smi_info": npu_info, "msprof": shutil.which("msprof")},
        "environment": {
            "ASCEND_HOME_PATH": os.environ.get("ASCEND_HOME_PATH"),
            "ASCEND_TOOLKIT_HOME": os.environ.get("ASCEND_TOOLKIT_HOME"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Path to write target_profile.json")
    args = parser.parse_args()

    profile = discover()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote target profile to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
