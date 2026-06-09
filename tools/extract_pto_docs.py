#!/usr/bin/env python3
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Load PTO documentation from https://pto-isa.github.io/ and emit instruction cards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from akg.pto_docs import load_from_site


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-url", default="https://pto-isa.github.io/", help="PTO ISA documentation root URL")
    parser.add_argument("--output-dir", default="docs_index/pto_instruction_cards")
    parser.add_argument("--max-pages", type=int, default=80)
    args = parser.parse_args()

    result = load_from_site(args.docs_url, Path(args.output_dir), max_pages=args.max_pages)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
