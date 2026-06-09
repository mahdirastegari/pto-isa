#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Run lightweight static legality checks for generated PTO-like kernel files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

KNOWN_INSTRUCTIONS = {
    "TLOAD",
    "TSTORE",
    "TADD",
    "TSUB",
    "TMUL",
    "TADDS",
    "TASSIGN",
    "TMULS",
    "TRELU",
    "TMAX",
    "TMIN",
    "TEXP",
    "TDIV",
    "TROWSUM",
    "TROWMAX",
    "TMATMUL",
}
INSTRUCTION_RE = re.compile(r"\b(T[A-Z][A-Z0-9_]*)\s*\(")


def check_kernel(kernel: Path, target: Path | None) -> tuple[bool, list[str]]:
    messages: list[str] = []
    if not kernel.exists():
        return False, [f"kernel file does not exist: {kernel}"]
    text = kernel.read_text(encoding="utf-8", errors="ignore")
    if target and not target.exists():
        messages.append(f"target profile does not exist: {target}")
    elif target:
        try:
            json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            messages.append(f"target profile is not valid JSON: {exc}")

    instructions = sorted(set(INSTRUCTION_RE.findall(text)))
    unknown = [instruction for instruction in instructions if instruction not in KNOWN_INSTRUCTIONS]
    if unknown:
        messages.append(f"unknown PTO instruction(s): {', '.join(unknown)}")
    if "TLOAD" in instructions and "TSTORE" not in instructions:
        messages.append("kernel loads tile data but does not store an output tile")
    if "TSTORE" in instructions and "TLOAD" not in instructions:
        messages.append("kernel stores tile data but does not load any input tile")
    if "tail" not in text.lower() and any(token in text for token in ["M", "N", "shape", "Shape"]):
        messages.append("tail handling is not documented in the kernel text")

    return not messages, messages or ["static check passed"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", required=True, help="Generated PTO kernel path")
    parser.add_argument("--target", help="Target profile JSON path")
    parser.add_argument("--log", help="Optional log output path")
    args = parser.parse_args()

    ok, messages = check_kernel(Path(args.kernel), Path(args.target) if args.target else None)
    output = "\n".join(messages) + "\n"
    if args.log:
        log = Path(args.log)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
