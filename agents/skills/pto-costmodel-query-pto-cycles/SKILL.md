---
name: PTO Costmodel Cycles Query Guide
description: This guide introduces how to use PTO Costmodel to obtain the number of simulation cycles of a single PTO ISA instruction, covering two usage scenarios of costmodel, query script usage, C++ templates for each instruction type, and compilation and running methods.
license: CANN Open Software License Agreement Version 2.0
---

# PTO Costmodel Cycles Query Guide

This guide describes how to use PTO Costmodel to obtain simulated cycles for PTO ISA instructions.

## Directory
1. [Overview](#overview)
2. [Confirmation of input information before query](#Confirmation of input information before query)
3. [Query single instruction Cycles](#Query single instruction-cycles)
4. [Generation method when script does not exist](#Generation method when script does not exist)
5. [Architecture Parameters](#Architecture Parameters)
6. [ST Test Suite](#st-testsuite)

## Overview

PTO costmodel is the performance simulation model of PTO ISA, which simulates the instruction execution time on Ascend NPU (A2/A3, `__NPU_ARCH__=2201`). It runs purely on CPU and does not require real hardware.

Core principle: When the `__COSTMODEL` macro is defined during compilation, `#include <pto/pto-inst.hpp>` will automatically replace all PTO instructions with the costmodel version. When the instructions are executed, the number of cycles will be recorded through the trace system (`BeginPtoInstr`/`EndPtoInstr` + `RecordCceCall`), and users can query it through the API.

**Capability boundary of current costmodel:**
- **Supported**: Single PTO ISA instruction level cycles query (such as the simulation time of a single instruction such as TADD and TMATMUL under the specified shape and dtype)
- **Not supported**: Performance simulation at the operator level (combination of multiple PTO instructions), this capability needs to be developed in the future

> **Important: The current costmodel only supports the A2/A3 platform (`__NPU_ARCH__=2201`), and the simulation results only reflect the performance characteristics of this platform. ** Results on other platforms may vary.

---

## Confirm the input information before querying

Before executing the query, **must confirm that the user has provided the following information**. If any item is missing, please proactively ask the user:

### General required information

| Information | Description | Example |
|------|------|------|
| **Instruction name** | The PTO instruction to be queried | `TADD`, `TMUL`, `TEXP`, `TMATMUL`, etc. |
| **Data type** | Tile element type | `float`, `half`, `bf16`, `int32`, `int16`, `int8`, `uint8` |
| **Tile Shape** | Number of rows and columns of Tile | `16x16`, `64x64`, `16x256`, etc. |

### Additional information for specific instructions

| Command type | Additional required information | Example |
|----------|-------------|------|
| **TCVT** | Source type + destination type (the two types are different) | source=`float`, destination=`half` |
| **TMATMUL** | A/B/Output three types + M/K/N three dimensions | A=`half`, B=`half`, Out=`float`, M=128, K=64, N=128 |

### Tips for missing information

- Missing instruction name: `"Which PTO instruction do you want to query the cycles of? (such as TADD, TMUL, TMATMUL, etc.)"`
- Missing data type: `"What is the data type? Support float/half/bf16/int32/int16/int8/uint8"`
- Missing shape: `"What is the shape of Tile? (such as 16x16, 64x64, 32x256)"`
- TMATMUL is missing dimensions: `"TMATMUL requires three dimensions: M, K, and N. Please provide specific values (such as M=128, K=64, N=128)"`
- TCVT missing type: `"TCVT needs to specify the source type and target type (such as float to half)"`

---

## Query a single instruction Cycles

### Use query script (recommended)

Script path: `tools/query_pto_cycles.py`

The script will automatically generate the smallest C++ file, compile and run, print cycles, and leave no residual files.

#### Usage

```bash
# Unary instructions (TEXP, TNEG, TRECIP, TRSQRT, TSQRT, TABS)
python3 tools/query_pto_cycles.py <command> <data type> -r <row> -c <column>

# Binary instructions (TADD, TSUB, TMUL, TDIV, TMAX, TMIN, TADDS, TSUBS, TMULS, TDIVS, TMAXS, TMINS, TSEL, TSELS, TCMP)
python3 tools/query_pto_cycles.py <command> <data type> -r <row> -c <column>

# Row Reduce instructions (TROWSUM, TROWMAX, TROWMIN)
python3 tools/query_pto_cycles.py <command> <data type> -r <row> -c <column>

# Col Reduce instructions (TCOLSUM, TCOLMAX, TCOLMIN)
python3 tools/query_pto_cycles.py <command> <data type> -r <row> -c <column>

# Type conversion (TCVT): first parameter = target type, second = source type
python3 tools/query_pto_cycles.py TCVT <target type> <source type> -r <row> -c <column>

# Matrix multiplication (TMATMUL): dtype1=A matrix type, dtype2=B matrix type, dtype3=output type
python3 tools/query_pto_cycles.py TMATMUL <A type> <B type> <Output type> --m <M> --k <K> --n <N>
```

#### Example

```bash
python3 tools/query_pto_cycles.py TEXP float -r 16 -c 16
# => [CYCLE] TEXP.float_16x16 actual=53

python3 tools/query_pto_cycles.py TADD half -r 64 -c 64
# => [CYCLE] TADD.half_64x64 actual=98

python3 tools/query_pto_cycles.py TROWSUM float -r 64 -c 64
# => [CYCLE] TROWSUM.float_64x64 actual=51

python3 tools/query_pto_cycles.py TCOLSUM half -r 16 -c 256
# => [CYCLE] TCOLSUM.half_16x256 actual=500

python3 tools/query_pto_cycles.py TCVT half float -r 16 -c 64
# => [CYCLE] TCVT.half<-float_16x64 actual=66

python3 tools/query_pto_cycles.py TMATMUL half half float --m 128 --k 64 --n 128
# => [CYCLE] TMATMUL.float<half,half>_128x64x128 actual=262
```

#### Supported data types

`float` / `fp32`, `half` / `fp16`, `bf16`, `int32`, `int16`, `int8`, `uint8`

#### Supported commands

| Category | Command |
|------|------|
| Unary | TEXP, TNEG, TRECIP, TRSQRT, TSQRT, TABS |
| Binary | TADD, TSUB, TMUL, TDIV, TMAX, TMIN, TMAXS, TMINS, TADDS, TSUBS, TMULS, TDIVS, TSEL, TSELS, TCMP |
| Row Reduce | TROWSUM, TROWMAX, TROWMIN |
| Col Reduce | TCOLSUM, TCOLMAX, TCOLMIN |
| Convert | TCVT |
| Matmul | TMATMUL |

## Generate method when the script does not exist

The script path is `tools/query_pto_cycles.py` in the project root directory. If it does not exist, follow the instructions below to create it.

The core logic of the script:
1. Determine the instruction signature from the predefined instruction classification (UNARY/BINARY/ROW_REDUCE/COL_REDUCE/CVT/MATMUL) based on the instruction name and data type entered by the user.
2. Use Python’s textwrap.dedent to generate the corresponding C++ source code. The core template is as follows:

### C++ templates for various types of instructions

`{dtype}`, `{rows}`, `{cols}`, `{instr}` are placeholders.

**Unary (single input):**
```cpp
#include <pto/pto-inst.hpp>
#include <pto/common/constants.hpp>
#include <pto/costmodel/trace.hpp>
#include <cstdio>
using namespace pto;
using namespace pto::mocker;
int main() {
    ResetTrace();
    using TileData = Tile<TileType::Vec, {dtype}, {rows}, {cols}, BLayout::RowMajor, -1, -1>;
    TileData srcTile({rows}, {cols});
    TileData dstTile({rows}, {cols});
    TASSIGN(srcTile, 0x0);
    TASSIGN(dstTile, 0x8000);
    {instr}(dstTile, srcTile); // For example: TEXP(dstTile, srcTile)
    uint64_t cycles = GetLastPtoInstrCycles();
    std::printf("[CYCLE] ... actual=%llu\n", (unsigned long long)cycles);
    return 0;
}
```

**Binary (dual input):**
```cpp
    // Same as above, but create src0Tile, src1Tile, dstTile
    {instr}(dstTile, src0Tile, src1Tile); // For example: TADD(dstTile, src0Tile, src1Tile)
```

**Row Reduce (row reduction, tmp required):**
```cpp
    //Create srcTile, tmpTile, dstTile (all rows x cols)
    {instr}(dstTile, srcTile, tmpTile); // For example: TROWSUM(dstTile, srcTile, tmpTile)
```

**Col Reduce (column reduction, dst is 1xcols):**
```cpp
    using SrcTile = Tile<TileType::Vec, {dtype}, {rows}, {cols}, BLayout::RowMajor, -1, -1>;
    using DstTile = Tile<TileType::Vec, {dtype}, 1, {cols}, BLayout::RowMajor, -1, -1>;
    // tmpTile shape = (rows/2 ? rows/2 : 1, cols)
    {instr}(dstTile, srcTile, tmpTile, false); // For example: TCOLSUM(dstTile, srcTile, tmpTile, false)
```

**TCVT (type conversion):**
```cpp
    using DstTile = Tile<TileType::Vec, {dst_dtype}, {rows}, {cols}, BLayout::RowMajor, -1, -1>;
    using SrcTile = Tile<TileType::Vec, {src_dtype}, {rows}, {cols}, BLayout::RowMajor, -1, -1>;
    TCVT(dstTile, srcTile, RoundMode::CAST_NONE);
```

**TMATMUL (Matrix Multiplication):**
```cpp
    constexpr int blockAlign = (sizeof({a_dtype}) == 1) ? 32 : 16;
    constexpr int M = CeilAlign({m}, blockAlign); // Same as N, K
    using LeftTile  = TileLeft<{a_dtype}, M, K, {m}, {k}>;
    using RightTile = TileRight<{b_dtype}, K, N, {k}, {n}>;
    using AccTile   = TileAcc<{out_dtype}, M, N, {m}, {n}>;
    TMATMUL(cTile, aTile, bTile);
```

### Compilation command

Write the generated `.cpp` into the temporary directory and compile it with the following command:

```bash
clang++ <src.cpp> -o <exe> -std=c++23 -O2 \
    -I<repo>/include -I<repo>/include/common \
    -D__COSTMODEL -D__NPU_ARCH__=2201 -DPTO_COMM_NOT_SUPPORTED \
    -Wno-macro-redefined -Wno-ignored-attributes
```

macOS additionally requires: `-isystem$(xcrun --show-sdk-path)/usr/include/c++/v1`

Run the executable file, parse the `[CYCLE]` lines in stdout, and output the results.

## Architecture parameters

- **Target Architecture**: A2/A3 Ascend NPU (`__NPU_ARCH__=2201`)
- **Main frequency**: 1.85 GHz
- **Compiler Requirements**: clang++ >= 15 or g++ >= 13, C++23
- **Required macro**: `-D__COSTMODEL -D__NPU_ARCH__=2201 -DPTO_COMM_NOT_SUPPORTED`
- **Header file path**: `-I<repo>/include -I<repo>/include/common`

## ST Test Suite

Formal regression tests are located in `tests/costmodel/st/testcase/` and are used to verify the correctness of costmodel.

### Operation mode

```bash
python3 tests/run_costmodel.py --testcase <name> --build-type Release
python3 tests/run_costmodel.py --build-type Release # Run all
```

### Available test cases

`tabs`, `tadd`, `tadds`, `tcmp`, `tcolmax`, `tcolmin`, `tcolsum`, `tcvt`, `tdiv`, `tdivs`, `texp`, `textract`, `tgather`, `tload`, `tloadconv`, `tmatmul`, `tmax`, `tmaxs`, `tmin`, `tmins`, `tmov`, `tmrgsort`, `tmul`, `tmuls`, `tneg`, `trecip`, `trowexpand`, `trowmax`, `trowmin`, `trowsum`, `trsqrt`, `tscatter`, `tsel`, `tsels`, `tsort32`, `tsqrt`, `tsub`, `tsubs`, `ttrans`
