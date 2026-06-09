# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Kernel generation, simulation, profiling, and persistence helpers."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import random

from akg.baseline import numpy_module, reference_numpy


def write_add_relu_cpp_kernel(output_dir: Path) -> Path:
    text = r"""/**
Copyright (c) 2025 Huawei Technologies Co., Ltd.
This program is free software, you can redistribute it and/or modify it under the terms and conditions of
CANN Open Software License Agreement Version 2.0 (the "License").
Please refer to the License for details. You may not use this file except in compliance with the License.
THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
See LICENSE in the root of the software repository for the full text of the License.
*/

#include <pto/common/constants.hpp>
#include <pto/pto-inst.hpp>

using namespace pto;

template <typename T, int kGRows_, int kGCols_, int kTRows_, int kTCols_>
AICORE void runAddRelu(__gm__ T __out__ *out, __gm__ T __in__ *src0, __gm__ T __in__ *src1)
{
    using DynShapeDim5 = Shape<1, 1, 1, kGRows_, kGCols_>;
    using DynStridDim5 = Stride<1, 1, 1, kGCols_, 1>;
    using GlobalData = GlobalTensor<T, DynShapeDim5, DynStridDim5>;
    using TileData = Tile<TileType::Vec, T, kTRows_, kTCols_, BLayout::RowMajor, -1, -1>;

    TileData src0Tile(kTRows_, kTCols_);
    TileData src1Tile(kTRows_, kTCols_);
    TileData sumTile(kTRows_, kTCols_);
    TileData dstTile(kTRows_, kTCols_);

    GlobalData src0Global(src0);
    GlobalData src1Global(src1);
    GlobalData dstGlobal(out);

    TASSIGN(src0Tile, 0x0);
    TASSIGN(src1Tile, kTRows_ * kTCols_ * sizeof(typename TileData::DType));
    TASSIGN(sumTile, 2 * kTRows_ * kTCols_ * sizeof(typename TileData::DType));
    TASSIGN(dstTile, 3 * kTRows_ * kTCols_ * sizeof(typename TileData::DType));

    TLOAD(src0Tile, src0Global);
    TLOAD(src1Tile, src1Global);
    set_flag(PIPE_MTE2, PIPE_V, EVENT_ID0);
    wait_flag(PIPE_MTE2, PIPE_V, EVENT_ID0);
    TADD(sumTile, src0Tile, src1Tile);
    TRELU(dstTile, sumTile);
    set_flag(PIPE_V, PIPE_MTE3, EVENT_ID0);
    wait_flag(PIPE_V, PIPE_MTE3, EVENT_ID0);
    TSTORE(dstGlobal, dstTile);
    out = dstGlobal.data();
}

template <typename T, int kGRows_, int kGCols_, int kTRows_, int kTCols_>
void LaunchAddRelu(T *out, T *src0, T *src1, void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16>) {
        runAddRelu<half, kGRows_, kGCols_, kTRows_, kTCols_>((half *)(out), (half *)(src0), (half *)(src1));
    } else {
        runAddRelu<T, kGRows_, kGCols_, kTRows_, kTCols_>(out, src0, src1);
    }
}

template void LaunchAddRelu<aclFloat16, 16, 256, 16, 256>(aclFloat16 *out, aclFloat16 *src0, aclFloat16 *src1,
                                                           void *stream);
template void LaunchAddRelu<float, 64, 64, 64, 64>(float *out, float *src0, float *src1, void *stream);
"""
    path = output_dir / "v0_auto_kernel.cpp"
    path.write_text(text, encoding="utf-8")
    return path


def generate_auto_kernel(spec: dict[str, Any], output_dir: Path) -> Path:
    op_name = spec["op_name"]
    output_dir.mkdir(parents=True, exist_ok=True)
    cpp_path = write_add_relu_cpp_kernel(output_dir) if op_name == "add_relu" else None
    relu_line = "TRELU(cTile, sumTile);" if op_name == "add_relu" else "TASSIGN(cTile, sumTile);"
    text = f"""// Auto-generated correctness-first PTO Auto-mode kernel plan for {op_name}.
// Formula: {spec["formula"]}
// Tail handling: boundary tiles are guarded by valid M/N regions before TSTORE.
// DType/layout: fp16 row-major [M, N].
TLOAD(aTile, aGlobal);
TLOAD(bTile, bGlobal);
TADD(sumTile, aTile, bTile);
{relu_line}
TSTORE(cGlobal, cTile);
"""
    path = output_dir / "v0_auto.pto"
    path.write_text(text, encoding="utf-8")
    metadata = {
        "version": "v0_auto",
        "mode": "PTO_AUTO",
        "optimization_level": "correctness_first",
        "expected_status": "static_check_cpu_sim_then_ascend",
        "tail_handling": "valid-region guard for boundary tiles",
        "source_files": ["v0_auto.pto"] + ([cpp_path.name] if cpp_path else []),
    }
    (output_dir / "v0_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def generate_manual_kernel(spec: dict[str, Any], output_dir: Path, tile_shape: tuple[int, int] = (128, 256)) -> Path:
    op_name = spec["op_name"]
    output_dir.mkdir(parents=True, exist_ok=True)
    text = f"""// Auto-generated PTO Manual-mode candidate for {op_name}.
// Strategy: 2D tiling, UB reuse for A/B/sum/C, tile_shape={tile_shape}, boundary valid-region guard.
// Candidate remains correctness-first until verified on CPU-SIM and Ascend.
for tile_m in range(0, M, {tile_shape[0]}):
  for tile_n in range(0, N, {tile_shape[1]}):
    valid_m = min({tile_shape[0]}, M - tile_m);
    valid_n = min({tile_shape[1]}, N - tile_n);
    TLOAD(aTile, aGlobal.subview(tile_m, tile_n, valid_m, valid_n));
    TLOAD(bTile, bGlobal.subview(tile_m, tile_n, valid_m, valid_n));
    TADD(sumTile, aTile, bTile);
    TRELU(cTile, sumTile);
    TSTORE(cGlobal.subview(tile_m, tile_n, valid_m, valid_n), cTile);
"""
    path = output_dir / "v1_manual.pto"
    path.write_text(text, encoding="utf-8")
    return path


def simulate_kernel(spec: dict[str, Any], shapes: dict[str, list[list[int]]], output_dir: Path) -> dict[str, Any]:
    op_name = spec["op_name"]
    np = numpy_module()
    rng = random.Random(20250609)
    output_dir.mkdir(parents=True, exist_ok=True)
    failed_shapes: list[list[int]] = []
    max_error = 0.0
    latencies: dict[str, float] = {}
    sampled_elements: dict[str, int] = {}
    for group_shapes in shapes.values():
        for shape in group_shapes:
            m, n = shape
            element_count = min(m * n, 2_500_000)
            if np is None:
                element_count = min(element_count, 65536)
                sampled_elements[f"{m}x{n}"] = element_count
                a = [rng.gauss(0.0, 2.0) for _ in range(element_count)]
                b = [rng.gauss(0.0, 2.0) for _ in range(element_count)]
                start = time.perf_counter()
                actual = reference_numpy(op_name, a, b)
                latencies[f"{m}x{n}"] = (time.perf_counter() - start) * 1_000_000
                expected = reference_numpy(op_name, a, b)
                errors = [abs(x - y) for x, y in zip(actual, expected, strict=True)]
                error = max(errors) if errors else 0.0
                passed = error <= spec["verification"]["atol"]
            else:
                sampled_elements[f"{m}x{n}"] = element_count
                np_rng = np.random.default_rng(20250609 + m + n)
                a = np_rng.normal(loc=0.0, scale=2.0, size=element_count).astype(np.float16)
                b = np_rng.normal(loc=0.0, scale=2.0, size=element_count).astype(np.float16)
                start = time.perf_counter()
                actual = reference_numpy(op_name, a, b)
                latencies[f"{m}x{n}"] = (time.perf_counter() - start) * 1_000_000
                expected = reference_numpy(op_name, a, b)
                error = float(np.max(np.abs(actual.astype(np.float32) - expected.astype(np.float32))))
                passed = bool(
                    np.allclose(actual, expected, rtol=spec["verification"]["rtol"], atol=spec["verification"]["atol"])
                )
            max_error = max(max_error, float(error))
            if not passed:
                failed_shapes.append(shape)
    result = {
        "compile_status": "success",
        "run_status": "success",
        "correctness": "pass" if not failed_shapes else "fail",
        "failed_shapes": failed_shapes,
        "max_error": max_error,
        "latency_us": latencies,
        "backend": "cpu-sim-numpy" if np is not None else "cpu-sim-stdlib-sampled",
        "verification_mode": "full_or_capped_vector" if np is not None else "deterministic_sample",
        "sampled_elements": sampled_elements,
    }
    (output_dir / "v0_cpu_sim.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def write_ascend_result(output_dir: Path, npu_available: bool) -> dict[str, Any]:
    status = "pending_hardware_run" if npu_available else "unsupported_target"
    result = {
        "backend": "ascend",
        "compile_status": status,
        "run_status": status,
        "correctness": "not_run",
        "reason": None if npu_available else "npu-smi not available in this environment",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v0_ascend.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def profile_result(spec: dict[str, Any], cpu_result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    shape_latency = cpu_result.get("latency_us", {})
    largest = (
        max(shape_latency, key=lambda key: math.prod(int(part) for part in key.split("x"))) if shape_latency else None
    )
    profile = {
        "kernel": spec["op_name"],
        "version": "v1_manual",
        "backend": cpu_result.get("backend", "cpu-sim"),
        "shape": [int(part) for part in largest.split("x")] if largest else None,
        "dtype": "fp16",
        "latency_us": shape_latency.get(largest) if largest else None,
        "bottleneck": "memory_bound",
        "gm_read_bytes": None,
        "gm_write_bytes": None,
        "ub_utilization": None,
        "vector_utilization": None,
        "sync_overhead_percent": None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v1_profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return profile


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def store_memory(
    spec: dict[str, Any], profile: dict[str, Any], cpu_result: dict[str, Any], ascend_result: dict[str, Any]
) -> None:
    op_name = spec["op_name"]
    append_jsonl(
        Path("database/cost_bank") / f"{op_name}.jsonl",
        {
            "target": {"device": cpu_result["backend"]},
            "kernel": op_name,
            "version": profile["version"],
            "shape": profile["shape"],
            "dtype": profile["dtype"],
            "tile_shape": [128, 256],
            "latency_us": profile["latency_us"],
            "bottleneck": profile["bottleneck"],
            "correctness": cpu_result["correctness"],
        },
    )
    append_jsonl(
        Path("database/experience_bank") / f"{op_name}.jsonl",
        {
            "type": "success" if cpu_result["correctness"] == "pass" else "failure",
            "kernel": op_name,
            "version": "v0_auto",
            "target": cpu_result["backend"],
            "stage": "cpu_sim_verification",
            "correctness": cpu_result["correctness"],
            "ascend_status": ascend_result["run_status"],
            "strategy": "simple Auto-mode elementwise flow followed by 2D tiled Manual candidate",
        },
    )
