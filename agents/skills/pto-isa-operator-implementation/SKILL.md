---
name: PTO-ISA Operator Implementation Guide
description: A complete process guide for using PTO-ISA to implement specified operator functions, covering ISA instruction selection, data flow analysis, instruction function explanation and kernel code generation
license: CANN Open Software License Agreement Version 2.0
---

# PTO-ISA Operator Implementation Guide

This guide provides complete process guidance for using PTO-ISA to implement specified operator functions.

## Directory
1. [Overview](#overview)
2. [Workflow](#workflow)
3. [Steps detailed explanation](#Steps detailed explanation)
4. [ISA instruction classification reference](#isa instruction classification reference)
5. [Data flow analysis framework](#data flow analysis framework)
6. [Example](#example)
7. [Best Practice](#bestpractice)
8. [FAQ](#FAQ)

## Overview

This skill is specifically designed to help developers select appropriate instructions from the PTO-ISA instruction set to implement specified operator functions and generate complete kernel code.

### Applicable scenarios

- Users specify specific operator functional requirements (such as: "Implementing GELU activation function", "Implementing Batch Normalization")
- Need to analyze the PTO-ISA instruction set and select the appropriate instruction combination
- Need to understand the flow of data on hardware
- Need to generate kernel code that can be used directly

### Key Features

- **ISA instruction selection**: Analyze and select the appropriate instruction from the PTOISA.md document
- **Data flow analysis**: Analyze data flow according to data processing sequence
  - **Vector calculation**: gm → ub → vector → ub → gm
  - **Cube calculation (matrix multiplication)**: GM → L1 → L0A/L0B → L0C → GM
- **Instruction Function Explanation**: Detailed explanation of the role of each ISA instruction in operator implementation
- **Code generation**: Output the complete kernel code implementation

### Quality gate driven by recent PR review

When developing or generating fusion operators, write the following checks into the implementation and tests first, rather than remediating them after review:

- **Synchronization and cross-core FIFO**: PR #61, #77, #85, #93, #95, #100 Repeated exposure to the combined risk of `TPUSH`/`TPOP`/`TFREE`, hook injection, `subblock_dim`, split lane and fine-grained sync. When it comes to these paths, at least C2V/V2C, split/no-split, `subblock_dim=1/2`, hook/no-hook, and target backends (CPU-SIM, A2/A3, A5) are covered.
- **Address, stride, layout**: Reviewers of PR #86 and #95 pointed out issues with ColMajor DN stride, golden data layout, `entryOffset` action position, and split-N subblock offset. Before writing TLOAD/TSTORE or partial tile transfer, first clarify the formulas of base offset, row offset, column offset, entry offset, split-lane offset, and verify it with golden case that can distinguish RowMajor/ColMajor/flattened rows/multi-column.
- **Template Contract**: PR #92 requires protecting constexpr tile-type dispatch with named constants and `static_assert`. When adding a new template or overloading it, you must clarify the constraints of the tile type, layout, dtype, and backend-only resources, and do not leave the magic number in the scheduling logic.
- **Test closed loop**: PR #85 exposed the problem of CMake registering a testcase directory that does not exist. When adding a new ST case, check: the directory exists, the local `CMakeLists.txt` exists, the parent CMake is registered, the gtest name is consistent with the output of `gen_data.py`, and the golden data can expose the target bug.
- **Performance Statement**: PR #100's chunked `TPUSH` benchmark shows that the number of synchronizations will directly affect performance. Any "faster" fusion paths are given backend, shape, command, and before/after numbers; hot loops are reviewed for contiguous, strided, split, and fallback paths respectively.

## Workflow

After the user specifies the operator function, follow the following workflow:

```
User specified operator function
    ↓
Step 1: Read PTOISA.md
    ↓
Step 2: Analyze operator requirements and list ISA instructions
    ↓
Step 3: Explain the instruction function in data flow sequence
    ↓
Step 4: Output kernel code implementation
```

## Detailed explanation of steps

### Step 1: Read the PTOISA.md document

**Goal**: Comprehensively understand the PTO-ISA instruction set and identify instruction categories that may be related to operators.

**Action**:
1. Reading document path: `pto-isa/docs/PTOISA.md`
2. Focus on the instruction index table and identify the following categories of instructions:
   - **Memory instructions**: TLOAD, TSTORE, TPREFETCH (GM <-> Tile data transfer)
   - **Element-wise calculation**: TADD, TSUB, TMUL, TDIV, TMAX, TMIN (Tile-Tile operation)
   - **Scalar operations**: TADDS, TSUBS, TMULS, TDIVS (Tile-scalar operations)
   - **Mathematical functions**: TLOG, TEXP, TSQRT, TRSQRT, TPOW (mathematical operations)
   - **Activation function**: TRELU, TPRELU, TLRELU (activation operation)
   - **Axis reduction/expansion**: TROWSUM, TCOLSUM, TROWMAX, TCOLMAX (axis operations)
   - **Broadcast operations**: TROWEXPANDADD, TCOLEXPANDADD (broadcast addition)
   - **Type Conversion**: TCVT (type conversion)
   - **Selection operation**: TSEL, TSELS (conditional selection)
   - **Matrix operations**: TMATMUL, TGEMV (matrix calculations)

3. Record each relevant instruction:
   - command name
   - Function description
   - Category
   - Applicable scenarios

**Output**: List of relevant ISA instructions

### Step 2: Organize and list the ISA instructions that need to be used

**Goal**: Determine specific ISA instruction combinations based on operator functional requirements.

**Analysis Framework**:

#### 2.1 Operator function decomposition

Decompose the operator function into basic operations:

| Operator type | Decomposition steps | Typical instructions |
|---------|---------|---------|
| Activation function | Input loading + calculation + output storage | TLOAD + TEXP/TLOG/TRELU + TSTORE |
| Reduce operation | Input load + reduce + output store | TLOAD + TROWSUM/TCOLSUM + TSTORE |
| Element-wise operation | Input load + operation + output storage | TLOAD + TADD/TSUB/TMUL/TDIV + TSTORE |
| Broadcast operation | Input load + broadcast + operation + storage | TLOAD + TROWEXPANDADD + TSTORE |
| Matrix operation (Cube) | Input loading + data transfer + matrix multiplication + output storage | TLOAD + TMOV + TMATMUL + TSTORE (GM→L1→L0A/L0B→L0C→GM) |
| Type conversion | Input load + conversion + output store | TLOAD + TCVT + TSTORE |
| Conditional operations | Input load + compare + select + store | TLOAD + TCMP + TSEL + TSTORE |

#### 2.2 ISA instruction selection principles

**Minimization principle**: Use the fewest instructions to complete the function and reduce data handling.

**Data flow optimization**:
- **Vector calculation**: Follow the basic data flow of gm → ub → vector → ub → gm
- **Cube calculation (matrix multiplication)**: Follow the matrix data flow of GM → L1 → L0A/L0B → L0C → GM

**Synchronization considerations**: Use Event synchronization or manual flag synchronization between instructions.

**Example**:

```
Operator: GELU activation function
GELU(x) = x * Φ(x) ≈ 0.5 * x * (1 + tanh(sqrt(2/π) * (x + 0.044715 * x^3)))

Instruction selection:
1. TLOAD: Load input x from GM to UB
2. TMUL: Calculate x^3 (x * x * x)
3. TMULS: Calculate 0.044715 * x^3 (scalar multiplication)
4. TADD: Calculate x + 0.044715 * x^3
5. TMULS: Calculate sqrt(2/π) * (x + ...) (scalar multiplication)
6. TEXP/TLOG: Calculate tanh function (optional, or use approximation)
7. TADD: Calculate 1 + tanh(...)
8. TMULS: Compute 0.5 * (result) (scalar multiplication)
9. TMUL: Calculate x * final result
10. TSTORE: Store results from UB to GM
```

**Output**: List of ISA instructions in order of execution

### Step 3: Explain the instruction function in detail according to the data processing sequence

**Goal**: Detail the role of each instruction in the data flow.

**Data Flow Framework**:

#### Vector calculation data flow

```
Data flow direction: gm → ub → vector → ub → gm
Phase 1: GM → UB (data loading, using TLOAD)
Stage 2: UB → Vector (calculation preparation)
Stage 3: Vector calculation (core calculation, using TADD/TMUL/TEXP, etc.)
Stage 4: Vector → UB (calculation result)
Stage 5: UB → GM (data storage, using TSTORE)
```

#### Cube calculation data flow (matrix multiplication)

```
Data flow direction: GM → L1 → L0A/L0B → L0C → GM
Phase 1: GM → L1 (matrix data loading, using TLOAD)
Phase 2: L1 → L0A/L0B (data transfer to matrix calculation unit, using TMOV)
Stage 3: Cube calculation (matrix multiplication, using TMATMUL, results to L0C)
Stage 4: L0C → GM (calculation result storage, using TSTORE)
```

**Key differences**:
- **Vector calculation**: Use UB (Unified Buffer) as the intermediate buffer to perform element-by-element operations
- **Cube calculation**: Use L1 and L0 buffers (L0A/L0B/L0C) to perform matrix multiplication operations

#### 3.1 Instruction function explanation template

For each instruction, explain it according to the following template:

```
Command: [command name]
Stage: [GM/UB/Vector stage]
Function: [Detailed function description]
Data flow: [Input → output data flow direction]
Example: [Specific usage example]
Synchronization requirements: [Whether synchronization is required and how to synchronize]
```

#### Detailed explanation of 3.2 stages

**Phase 1: GM → UB (data loading)**

```
Command: TLOAD
Function: Load data from GlobalTensor (GM) to Tile (UB)
Data flow: GlobalMemory[srcGlobal] → UnifiedBuffer[srcTile]
Input: GlobalTensor object, describing the data layout on GM
Output: Tile object, which stores the data loaded into UB
Synchronization requirements:
  - It is recommended to use Event synchronization: Event<Op::TLOAD, Op::NextOp>
  - Or manual synchronization: set_flag(PIPE_MTE2, PIPE_V, EVENT_ID0)

Example:
TLOAD(srcTile, srcGlobal);
event0 = TLOAD(src1Tile, src1Global); // Return with Event
```

**Phase 2/3: Vector calculation (core calculation)**

According to the specific operator, select the corresponding calculation instruction:

```
Element-wise addition: TADD
Function: Element-wise addition of two Tiles
Data flow: UB[src0Tile] + UB[src1Tile] → UB[dstTile]
Input: Two source Tiles
Output: a target Tile
Synchronization requirements: Event<Op::TLOAD, Op::TADD>

Example:
event1 = TADD(dstTile, src0Tile, src1Tile, event0);
```

```
Scalar multiplication: TMULS
Function: Element-wise multiplication of Tile and scalar
Data flow: UB[srcTile] * scalar → UB[dstTile]
Input: a source Tile + a scalar value
Output: a target Tile
Synchronization requirements: Event<Op::PreviousOp, Op::TMULS>

Example:
event2 = TMULS(dstTile, srcTile, (T)scalar, event1);
```

```
Exponential operation: TEXP
Function: Tile’s element-wise exponential operation (e^x)
Data flow: exp(UB[srcTile]) → UB[dstTile]
Input: a source Tile
Output: a target Tile
Synchronization requirements: Event<Op::PreviousOp, Op::TEXP>

Example:
event3 = TEXP(dstTile, srcTile, event2);
```

```
Maximum value selection: TMAX
Function: Element-wise maximum value of two Tiles
Data flow: max(UB[src0Tile], UB[src1Tile]) → UB[dstTile]
Input: Two source Tiles
Output: a target Tile
Synchronization requirements: Event<Op::PreviousOp, Op::TMAX]

Example:
event4 = TMAX(dstTile, src0Tile, src1Tile, event3);
```

**Cube calculation phase: matrix multiplication (GM → L1 → L0A/L0B → L0C → GM)**

```
Matrix multiplication: TMATMUL
Function: Matrix multiplication calculation C = A * B
Data flow:
  - GM → L1: GlobalMemory[Matrix A/B] → L1Buffer[MatTile] (TLOAD)
  - L1 → L0A/L0B: L1Buffer[MatTile] → L0Buffer[Left/RightTile] (TMOV)
  - L0A/L0B → L0C: Matrix multiplication calculation (TMATMUL)
  - L0C → GM: L0Buffer[AccTile] → GlobalMemory[result] (TSTORE)
Input: Matrices A and B (loaded via MatTile)
Output: matrix C (stored via AccTile)
Synchronization requirements:
  - After TLOAD is completed: Event<Op::TLOAD, Op::TMOV> or set_flag(PIPE_MTE2, PIPE_MTE1)
  - After TMOV is completed: Event<Op::TMOV, Op::TMATMUL> or set_flag(PIPE_MTE1, PIPE_M)
  - After TMATMUL is completed: Event<Op::TMATMUL, Op::TSTORE_VEC> or set_flag(PIPE_M, PIPE_FIX)

Example:
// 1. Load matrix into L1
TLOAD(aMatTile, src0Global);
TLOAD(bMatTile, src1Global);

// 2. Move data to L0A/L0B
#ifndef __PTO_AUTO__
    set_flag(PIPE_MTE2, PIPE_MTE1, EVENT_ID0);
    wait_flag(PIPE_MTE2, PIPE_MTE1, EVENT_ID0);
#endif
TMOV(aTile, aMatTile);
TMOV(bTile, bMatTile);

// 3. Matrix multiplication calculation
#ifndef __PTO_AUTO__
    set_flag(PIPE_MTE1, PIPE_M, EVENT_ID0);
    wait_flag(PIPE_MTE1, PIPE_M, EVENT_ID0);
#endif
TMATMUL(cTile, aTile, bTile);

// 4. Store the result
#ifndef __PTO_AUTO__
    set_flag(PIPE_M, PIPE_FIX, EVENT_ID0);
    wait_flag(PIPE_M, PIPE_FIX, EVENT_ID0);
#endif
TSTORE(dstGlobal, cTile);
```

**Phase 5: UB → GM (data storage)**

```
Command: TSTORE
Function: Store Tile data to GlobalTensor (GM)
Data flow: UnifiedBuffer[dstTile] → GlobalMemory[dstGlobal]
Input: Tile object, data on UB
Output: GlobalTensor object, data on GM
Synchronization requirements:
  - It is recommended to use Event synchronization: Event<Op::LastOp, Op::TSTORE_VEC>
  - Or manual synchronization: set_flag(PIPE_V, PIPE_MTE3, EVENT_ID0)

Example:
TSTORE(dstGlobal, dstTile, eventLast);
```

**Output**: Complete instruction function explanation document in data flow sequence

### Step 4: Output kernel code implementation

**Goal**: Generate complete, runnable kernel code.

**Code structure**:

```cpp
/**
Copyright (c) 2025 Huawei Technologies Co., Ltd.
...
*/

#include <pto/pto-inst.hpp>
#include "acl/acl.h"

using namespace pto;

namespace OperatorName {

// ==================== Device function ====================
template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
__global__ AICORE void runOperator(__gm__ T *out, __gm__ T *src0, ...)
{
    // 1. Type definition
    using DynShapeDim5 = Shape<1, 1, 1, vRows, vCols>;
    using DynStrideDim5 = Stride<1, 1, 1, vCols, 1>;
    using GlobalData = GlobalTensor<T, DynShapeDim5, DynStrideDim5>;
    using TileData = Tile<TileType::Vec, T, kTRows_, kTCols_, BLayout::RowMajor, -1, -1>;

    // 2. Tile and GlobalTensor declaration
    TileData src0Tile(vRows, vCols);
    TileData dstTile(vRows, vCols);
    TASSIGN(src0Tile, 0x0);
    TASSIGN(dstTile, sizeof(T) * TileData::Numel);

    GlobalData src0Global(src0);
    GlobalData dstGlobal(out);

    // 3. Event declaration (event synchronization is recommended)
    Event<Op::TLOAD, Op::CALC_OP> event0;
    Event<Op::CALC_OP, Op::TSTORE_VEC> event1;

    // 4. Data loading (gm → ub)
    event0 = TLOAD(src0Tile, src0Global);

    // 5. Core calculation (vector calculation)
    event1 = CALC_OP(dstTile, src0Tile, ..., event0);

    // 6. Data storage (ub → gm)
    TSTORE(dstGlobal, dstTile, event1);

    out = dstGlobal.data();
}

// ==================== Host function ====================
template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
void launchOperator(T *out, T *src0, ..., void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16>) {
        runOperator<half, kTRows_, kTCols_, vRows, vCols>
            <<<1, nullptr, stream>>>((half *)out, (half *)src0, ...);
    } else {
        runOperator<T, kTRows_, kTCols_, vRows, vCols><<<1, nullptr, stream>>>(out, src0, ...);
    }
}

// ==================== Template instantiation ====================
template void launchOperator<float, 64, 64, 64, 64>(float *out, float *src0, ..., void *stream);
template void launchOperator<aclFloat16, 16, 256, 16, 256>(aclFloat16 *out, aclFloat16 *src0, ..., void *stream);

} // namespace OperatorName
```

**Key points for code generation**:

1. **Naming convention**: The kernel file is named `t<operation command>_kernel.cpp`
2. **Template parameters**: T (data type), kTRows_, kTCols_ (Tile dimensions), vRows, vCols (valid data dimensions)
3. **Type conversion**: aclFloat16 needs to be converted to half type
4. **Buffer Allocation**: Use TASSIGN to tightly arrange Tile addresses
5. **Synchronization strategy**: It is recommended to use Event synchronization, and manual logo synchronization is an alternative.
6. **Template Instantiation**: Provide instantiation for common configurations

**Output**: Complete kernel code file

## ISA instruction classification reference

### Memory instructions (GM <-> Tile)

| Command | Function | Data flow | Applicable scenarios |
|------|------|--------|---------|
| TLOAD | GM → UB/L1 | GlobalMemory → UnifiedBuffer/L1Buffer | Vector and Cube calculations |
| TSTORE | UB/L0C → GM | UnifiedBuffer/L0Buffer → GlobalMemory | Vector and Cube calculations |
| TPREFETCH | Prefetch to UB cache | Prompt prefetch | Vector calculation optimization |
| MGATHER | Index collection loading | GM[index] → UB | Vector calculation |
| MSCATTER | Index spread storage | UB → GM[index] | Vector calculation |

**Note**:
- TLOAD can be loaded into UB (Vector calculation) or L1Buffer (Cube calculation)
- TSTORE can store UB (Vector calculation) or L0C (Cube calculation) data

### Element-by-element calculation instructions (Tile-Tile)

| Command | Function | Expression |
|------|------|--------|
| TADD | Element-wise addition | dst = src0 + src1 |
| TSUB | Element-wise subtraction | dst = src0 - src1 |
| TMUL | Element-wise multiplication | dst = src0 * src1 |
| TDIV | Element-wise division | dst = src0 / src1 |
| TMAX | Element-wise maximum value | dst = max(src0, src1) |
| TMIN | Element-wise minimum value | dst = min(src0, src1) |
| TCMP | compare (generate mask) | predicate = cmp(src0, src1) |
| TSHL | Element-wise left shift | dst = src0 << src1 |
| TSHR | Element-wise right shift | dst = src0 >> src1 |
| TAND | Element-wise bitwise AND | dst = src0 & src1 |
| TOR | Element-wise bitwise OR | dst = src0 | src1 |
| TXOR | Element-wise bitwise XOR | dst = src0 ^ src1 |
| TNOT | Element-wise bitwise negation | dst = ~src |

### Scalar operation instructions (Tile-scalar)

| Command | Function | Expression |
|------|------|--------|
| TADDS | Tile plus scalar | dst = src + scalar |
| TSUBS | Tile minus scalar | dst = src - scalar |
| TMULS | Tile multiplied by scalar | dst = src * scalar |
| TDIVS | Tile divide scalar | dst = src/scalar |
| TMINS | Tile and scalar minimum | dst = min(src, scalar) |
| TMAXS | Tile and scalar maximum | dst = max(src, scalar) |
| TCMPS | Tile vs. scalar comparison | predicate = cmp(src, scalar) |
| TEXPANDS | Scalar broadcast to Tile | dst = broadcast(scalar) |

### Math function instructions

| Command | Function | Expression |
|------|------|--------|
| TLOG | natural logarithm | dst = log(src) |
| TEXP | Exponential operation | dst = exp(src) |
| TSQRT | square root | dst = sqrt(src) |
| TRSQRT | Reciprocal square root | dst = 1/sqrt(src) |
| TPOW | Power operation | dst = src0 ^ src1 |
| TRECIP | reciprocal | dst = 1/src |
| TABS | Absolute value | dst = abs(src) |
| TNEG | Negative | dst = -src |

### Activate function instructions

| Command | Function | Expression |
|------|------|--------|
| TRELU | ReLU | dst = max(0, src) |
| TPRELU | PReLU | dst = max(0, src) + slope * min(0, src) |
| TLRELU | Leaky ReLU (scalar slope) | dst = max(0, src) + scalar * min(0, src) |

### Axis reduction/expansion instructions

| Command | Function | Operation |
|------|------|------|
| TROWSUM | Sum of rows | Sum of all columns in each row |
| TROWPROD | row product | product of all columns in each row |
| TROWMAX | Row maximum value | Maximum value of all columns in each row |
| TROWMIN | row minimum value | minimum value of all columns in each row |
| TROWARGMAX | row argmax | maximum value column index for each row |
| TROWARGMIN | row argmin | minimum value column index for each row |
| TCOLSUM | Sum of columns | Sum of all rows in each column |
| TCOLPROD | column product | product of all rows per column |
| TCOLMAX | Maximum value of column | Maximum value of all rows in each column |
| TCOLMIN | Column minimum value | Minimum value of all rows in each column |
| TCOLARGMAX | Column argmax | Maximum row index of each column |
| TCOLARGMIN | Column argmin | Minimum value row index for each column |
| TROWEXPAND | Row broadcast | Broadcast the first element of the row to the entire row |
| TCOLEXPAND | Column broadcast | Broadcast the first element of the column to the entire column |

### Broadcast operation instructions

| Command | Function | Operation |
|------|------|------|
| TROWEXPANDADD | row broadcast addition | + broadcast scalar vector per row |
| TROWEXPANDSUB | row broadcast subtraction | each row - broadcast scalar vector |
| TROWEXPANDMUL | row broadcast multiplication | * broadcast scalar vector per row |
| TROWEXPANDDIV | row broadcast division | per row / broadcast scalar vector |
| TROWEXPANDMAX | Row broadcast maximum value | max(each row, broadcast scalar vector) |
| TROWEXPANDMIN | row broadcast minimum value | min(each row, broadcast scalar vector) |
| TROWEXPANDEXPDIF | Row exponent difference | exp(each row - broadcast scalar vector) |
| TCOLEXPANDADD | column broadcast addition | + broadcast scalar vector per column |
| TCOLEXPANDSUB | column broadcast subtraction | per column - broadcast scalar vector |
| TCOLEXPANDMUL | Column broadcast multiplication | * Broadcast scalar vector per column |
| TCOLEXPANDDIV | column broadcast division | per column / broadcast scalar vector |
| TCOLEXPANDMAX | Column broadcast maximum value | max(each column, broadcast scalar vector) |
| TCOLEXPANDMIN | Column broadcast minimum value | min(each column, broadcast scalar vector) |
| TCOLEXPANDEXPDIF | Column exponential difference | exp(each column - broadcast scalar vector) |

### Data movement instructions (buffer data movement)

| Command | Function | Data flow | Applicable scenarios |
|------|------|--------|---------|
| TMOV | L1 → L0A/L0B | MatTile → LeftTile/RightTile | Cube calculation (matrix multiplication) |
| TMOV | Move between Tiles | srcTile → dstTile | Data format conversion |
| TMOV_FP | Movement with scale | srcTile * scale → dstTile | Quantization operation |
| TRESHAPE | Tile reinterpretation | Keep bytes, change type/shape | Type conversion |
| TTRANS | Tile transpose | srcTile^T → dstTile | Matrix transpose |

**The key role of TMOV in matrix multiplication**:
- Move the MatTile data of L1Buffer to L0Buffer
- Prepare LeftTile and RightTile for use by Cube computing unit
- Data flow: L1 → L0A/L0B → TMATMUL → L0C

### Type conversion and selection instructions

| Command | Function | Operation |
|------|------|------|
| TCVT | Type conversion | src_type → dst_type |
| TSEL | Condition selection (Tile) | mask ? src0 : src1 |
| TSELS | conditional selection (Tile-scalar) | mask ? src : scalar |

### Matrix operation instructions (using Cube core)

**Important**: Matrix operations use the Cube core, and the data flow is **GM → L1 → L0A/L0B → L0C → GM**

| Command | Function | Data Flow | Expression |
|------|------|--------|--------|
| TLOAD | GM → L1 | GlobalMemory → L1Buffer (load matrix data) | MatTile loading |
| TMOV | L1 → L0A/L0B | L1Buffer → L0Buffer (moved to computing unit) | MatTile → LeftTile/RightTile |
| TMATMUL | L0A/L0B → L0C | Cube matrix multiplication calculation | C = A * B |
| TSTORE | L0C → GM | L0Buffer → GlobalMemory (storage result) | AccTile → GlobalMemory |
| TMATMUL_ACC | Matrix multiplication (accumulation) | L0A/L0B → L0C (with accumulation) | C = A * B + C |
| TMATMUL_BIAS | Matrix multiplication (plus bias) | L0A/L0B → L0C + bias | C = A * B + bias |
| TGEMV | Matrix-vector multiplication | L0A/L0B → L0C | y = A * x |
| TGEMV_ACC | Matrix-vector multiplication (accumulation) | L0A/L0B → L0C (with accumulation) | y = A * x + y |
| TGEMV_BIAS | Matrix-vector multiplication (plus bias) | L0A/L0B → L0C + bias | y = A * x + bias |

**Matrix multiplication complete data flow example**:
```
GM → L1 (TLOAD) → L0A/L0B (TMOV) → L0C (TMATMUL) → GM (TSTORE)

Detailed steps:
1. TLOAD: Load matrices A and B from GM to L1Buffer (MatTile)
2. TMOV: Move MatTile data to L0Buffer (LeftTile and RightTile)
3. TMATMUL: Perform matrix multiplication in the Cube core and store the result in L0C (AccTile)
4. TSTORE: Store AccTile results to GM
```

### Ternary operation instructions

| Command | Function | Expression |
|------|------|--------|
| TADDC | Ternary addition | dst = src0 + src1 + src2 |
| TSUBC | Ternary subtraction | dst = src0 - src1 + src2 |
| TADDSC | Tile+scalar+Tile addition | dst = src0 + scalar + src1 |
| TSUBSC | Tile-scalar + Tile operation | dst = src0 - scalar + src1 |

## Data flow analysis framework

### Basic data flow mode

#### Vector calculation data flow (element-by-element operation)

```
┌─────────────────────────────────────────────────────────────┐
│ Vector calculation data flow (gm → ub → vector → ub → gm) │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GlobalMemory (GM)                                           │
│       │                                                      │
│       │ TLOAD                                                │
│       ↓                                                      │
│  UnifiedBuffer (UB)                                          │
│       │                                                      │
│ │ Calculation instructions (TADD/TMUL/TEXP, etc.) │
│       ↓                                                      │
│ Vector calculation unit │
│       │                                                      │
│ │ Calculation results │
│       ↓                                                      │
│  UnifiedBuffer (UB)                                          │
│       │                                                      │
│       │ TSTORE                                               │
│       ↓                                                      │
│  GlobalMemory (GM)                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Cube calculation data flow (matrix multiplication)

```
┌─────────────────────────────────────────────────────────────┐
│ Cube calculation data flow (GM → L1 → L0 → GM) │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GlobalMemory (GM)                                           │
│       │                                                      │
│       │ TLOAD                                                │
│       ↓                                                      │
│  L1Buffer (L1)                                               │
│       │                                                      │
│       │ TMOV                                                 │
│       ↓                                                      │
│  L0Buffer (L0A/L0B)                                          │
│       │                                                      │
│       │ TMATMUL                                              │
│       ↓                                                      │
│  L0Buffer (L0C)                                              │
│       │                                                      │
│       │ TSTORE                                               │
│       ↓                                                      │
│  GlobalMemory (GM)                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**The difference between the two data streams**:

| Features | Vector calculation | Cube calculation |
|------|-----------|----------|
| Calculation Unit | Vector Unit (PIPE_V) | Matrix Unit (PIPE_M) |
| Intermediate buffer | UnifiedBuffer (UB) | L1Buffer + L0Buffer (L0A/L0B/L0C) |
| Applicable scenarios | Element-by-element operations (TADD/TMUL/TEXP, etc.) | Matrix multiplication (TMATMUL) |
| Data flow path | GM → UB → V → UB → GM | GM → L1 → L0A/L0B → L0C → GM |
| Synchronous pipeline | MTE2 → V → MTE3 | MTE2 → MTE1 → M → FIX → MTE3 |

### Synchronization mechanism

**Event synchronization (recommended)**:
```cpp
Event<Op::TLOAD, Op::TADD> event0;
Event<Op::TADD, Op::TSTORE_VEC> event1;

event0 = TLOAD(srcTile, srcGlobal); // event0 triggers when TLOAD is completed
event1 = TADD(dstTile, src0Tile, src1Tile, event0); // Wait for event0 and trigger event1 after completion
TSTORE(dstGlobal, dstTile, event1); // Wait for event1
```

**Manual Logo Synchronization**:
```cpp
TLOAD(src0Tile, src0Global);
TLOAD(src1Tile, src1Global);

#ifndef __PTO_AUTO__
    set_flag(PIPE_MTE2, PIPE_V, EVENT_ID0); // MTE2 (memory loading) → V (vector calculation)
    wait_flag(PIPE_MTE2, PIPE_V, EVENT_ID0); // Wait for memory loading to complete
#endif

TADD(dstTile, src0Tile, src1Tile);

#ifndef __PTO_AUTO__
    set_flag(PIPE_V, PIPE_MTE3, EVENT_ID0); // V (vector calculation) → MTE3 (memory storage)
    wait_flag(PIPE_V, PIPE_MTE3, EVENT_ID0); // Wait for calculation to complete
#endif

TSTORE(dstGlobal, dstTile);
```

### Pipeline stage

| Assembly line | Abbreviation | Function | Applicable scenarios |
|--------|------|------|---------|
| Memory Transfer Engine 1 | PIPE_MTE1 | Matrix data transfer (L1 → L0) | Cube calculation (matrix multiplication) |
| Memory Transfer Engine 2 | PIPE_MTE2 | Vector/Matrix data loading (GM → UB/L1) | Vector and Cube calculations |
| Memory Transfer Engine 3 | PIPE_MTE3 | Data Storage (UB/L0C → GM) | Vector and Cube Computation |
| Vector Unit | PIPE_V | Vector calculation (element-by-element operation) | Vector calculation (TADD/TMUL, etc.) |
| Matrix Unit | PIPE_M | Matrix calculation (matrix multiplication) | Cube calculation (TMATMUL) |
| Fix Unit | PIPE_FIX | Format conversion | Cube calculation result formatting |
| Scalar Unit | PIPE_S | Scalar calculations | Scalar operations |
| All Pipelines | PIPE_ALL | All Pipelines | Global Synchronization |

**Pipeline synchronization strategy**:
- **Vector calculation**: MTE2 (GM → UB) → V (calculation) → MTE3 (UB → GM)
- **Cube calculation**: MTE2 (GM → L1) → MTE1 (L1 → L0) → M (calculation) → FIX (format conversion) → MTE3 (L0 → GM)

### Inter-core synchronization mechanism (TPUSH/TPOP)

**Important**: Data transmission between Cube core and Vector core must use TPUSH/TPOP, simple TMOV cannot be used.

#### Inter-core synchronization architecture

```
┌─────────────────────────────────────────────┐
│         A5 AI Core Architecture             │
├─────────────────────────────────────────────┤
│                                              │
│  ┌──────────────┐  ┌──────────────────┐     │
│  │  Cube Core   │  │  Vector Core 0   │     │
│  │  (PIPE_M)    │  │  (PIPE_V)        │     │
│  │  L1/L0       │  │  UB              │     │
│  └              │  │                  │     │
│  │  TPUSH (C2V) │  │  TPOP (C2V)      │     │
│  │  TPOP (V2C)  │  │  TPUSH (V2C)     │     │
│  └              │  │                  │     │
│  └──────────────┘  └──────────────────┘     │
│                                              │
│  ┌──────────────────┐                       │
│  │  Vector Core 1   │                       │
│  │  (PIPE_V)        │                       │
│  │  UB              │                       │
│  │                  │                       │
│  │  TPOP (C2V)      │                       │
│  │  TPUSH (V2C)     │                       │
│  │                  │                       │
│  └──────────────────┘                       │
│                                              │
│ Inter-core synchronization: TPUSH → TPOP → TFREE │
│                                              │
└─────────────────────────────────────────────┘
```

#### Inter-core synchronization direction type

| Direction Type | Definition | Data Flow | Producer Pipeline | Consumer Pipeline |
|---------|------|--------|-------------|-------------|
| **DIR_C2V** | Cube → Vector | L0C → UB | PIPE_FIX | PIPE_V |
| **DIR_V2C** | Vector → Cube | UB → L1 | PIPE_MTE3 | PIPE_MTE1 |
| **DIR_BOTH** | Bidirectional | L0C ↔ UB | PIPE_FIX + PIPE_MTE3 | PIPE_V + PIPE_MTE1 |

#### Vector/Cube core code distinguishes macro definitions

**Important**: PTO-ISA uses compiler macros to distinguish the execution paths of Vector cores and Cube cores. The same kernel code will be compiled twice to generate executable files for the Vector core and Cube core respectively.

**Macro definition mode**:

```cpp
// The compiler automatically defines the following macros when compiling different cores:
// - When compiling Vector core: define __DAV_VEC__
// - When compiling Cube core: define __DAV_CUBE__

#ifdef __DAV_CUBE__
constexpr bool DAV_CUBE = true;
#else
constexpr bool DAV_CUBE = false;
#endif

#ifdef __DAV_VEC__
constexpr bool DAV_VEC = true;
#else
constexpr bool DAV_VEC = false;
#endif
```

**Usage Example**:

```cpp
template <typename T, int M, int K, int N>
__global__ AICORE void runOperator(__gm__ T *out, __gm__ T *srcA, __gm__ T *srcB)
{
    // Vector core execution path
    if constexpr (DAV_VEC) {
        // Vector calculation: element-by-element operation, activation function, reduction, etc.
        TLOAD(vecTile, srcGlobal);
        TADD(dstTile, src0Tile, src1Tile);
        
        // V2C: TPUSH data to Cube core
        TPUSH<V2CPipe, VecTileNZ, TileSplitAxis::TILE_NO_SPLIT>(pipe, vecTile);
        
        // C2V: TPOP receives data from Cube core
        TPOP<C2VPipe, VecTile, TileSplitAxis::TILE_NO_SPLIT>(pipe, recvTile);
        TFREE<C2VPipe, TileSplitAxis::TILE_NO_SPLIT>(pipe);
        
        TSTORE(dstGlobal, dstTile);
    }
    
    //Cube core execution path
    if constexpr (DAV_CUBE) {
        // Cube calculation: matrix multiplication
        TLOAD(matTileA, srcAGlobal);
        TLOAD(matTileB, srcBGlobal);
        
        // V2C: TPOP receives data from the Vector core
        TPOP<V2CPipe, MatTile, TileSplitAxis::TILE_NO_SPLIT>(pipe, matTileB);
        TFREE<V2CPipe, TileSplitAxis::TILE_NO_SPLIT>(pipe);
        
        TMOV(leftTile, matTileA);
        TMOV(rightTile, matTileB);
        TMATMUL(accTile, leftTile, rightTile);
        
        // C2V: TPUSH data to Vector core
        TPUSH<C2VPipe, AccTile, TileSplitAxis::TILE_NO_SPLIT>(pipe, accTile);
        
        TSTORE(dstGlobal, accTile);
    }
}
```

**Macro definition rules**:

| Macro name | Definition timing | Applicable scenarios |
|--------|---------|---------|
| `__DAV_VEC__` | When compiling Vector core | Vector calculation, UB operation, PIPE_V pipeline |
| `__DAV_CUBE__` | When compiling Cube core | Cube calculation, L1/L0 operation, PIPE_M pipeline |

**Note**:
1. Use `if constexpr (DAV_VEC)` and `if constexpr (DAV_CUBE)` for branch judgment
2. Do not mix Tile types of another core in the execution path of the same core
3. TPUSH/TPOP must be used in pairs: Vector core TPUSH corresponds to Cube core TPOP
4. TFREE must be called to release the buffer after each TPOP

#### TPUSH three-step process

TPUSH is used by the producer core to push data to the consumer core:

**Step 1: Alloc (Allocate Space)**
- The producer core waits for the consumer core to release space
- C2V: `wait_intra_block(PIPE_FIX, FlagID+1)`
- V2C: `wait_intra_block(PIPE_MTE3, FlagID+1)`

**Step 2: Store (write data)**
- Select the handling method based on TileType and FIFO type
- AccTile → VecFIFO: `pushAcc2VecFiFo` (L0C → UB)
- VecTile → MatFIFO: `pushVec2MatFiFo` (UB → L1)

**Step 3: Commit (Signal Notification)**
- Notify consumers that core data is ready
- C2V: `set_intra_block(PIPE_FIX, FlagID)`
- V2C: `set_intra_block(PIPE_MTE3, FlagID)`

#### TPOP three-step process

TPOP is used by the consumer core to read data from the producer core:

**Step 1: Wait (wait for data)**
- The consumer core waits for the producer core data to be ready
- C2V: `wait_intra_block(PIPE_V, FlagID)`
- V2C: `wait_intra_block(PIPE_MTE1, FlagID)`

**Step 2: Pop (read data)**
- Select the reading method based on TileType and FIFO type
- VecFIFO → VecTile: `popTileFromVecFiFo`
- MatFIFO → MatTile: `popTileFromMatFiFo`

**Step 3: Free**
- Notify the producer that core space has been released
- Use the TFREE instruction

#### TPipe structure definition

```cpp
template <uint8_t FlagID, uint8_t DirType, uint32_t SlotSize, uint32_t SlotNum>
using TPipe = TPipe<FlagID, DirType, SlotSize, SlotNum>;

// Parameter description:
// FlagID: Inter-core synchronization flag ID (0-7)
// DirType: Communication direction (DIR_C2V=1, DIR_V2C=2, DIR_BOTH=3)
// SlotSize: FIFO slot size (bytes)
// SlotNum: Number of FIFO slots (2 is recommended)

//TPipe initialization:
// GM_SLOT_BUFFER: GM FIFO base address
// C2V_CONSUMER_BUF: Cube→Vec consumer UB address
// V2C_CONSUMER_BUF: Vec→Cube consumer L1 address
using MatPipe = TPipe<FLAG_ID, Direction::DIR_C2V, sizeof(T) * M * N, 2>;
MatPipe mPipe((__gm__ void *)(uint64_t)0x0, (uint32_t)0x0, (uint32_t)0x20000);
```

#### TileSplitAxis tile mode

| SplitAxis | Description | Vector core allocation |
|-----------|------|------------|
| **TILE_UP_DOWN** | Blocking along the row | Vec0 processes the upper half, Vec1 processes the lower half |
| **TILE_LEFT_RIGHT** | Blocking along columns | Vec0 processes the left half, Vec1 processes the right half |
| **TILE_NO_SPLIT** | No blocking | Single Vector core processes all |

#### FlagID allocation strategy

The A5 architecture provides **8 FlagID** (0-7) for inter-core synchronization:

| FlagID | Purpose | Description |
|--------|------|------|
| **FlagID** | Data ready signal | Producer setting, consumer waiting |
| **FlagID+1** | Space release signal | Consumer settings, producers wait |
| **FlagID+16** | Vec core 1 signal | Used when dual Vector cores |

**FlagID allocation when using dual Vector cores**:
```
Vec0: FlagID (main core)
Vec1: FlagID+16 (slave core)

Cube core needs to wait for dual core:
wait_intra_block(PIPE_FIX, FlagID); // Vec0 signal
wait_intra_block(PIPE_FIX, FlagID+16); // Vec1 signal
```

#### Best practices for inter-core synchronization

**1. FlagID management**: Assign an independent FlagID to each TPipe to avoid conflicts

**2. FIFO depth setting**: It is recommended to use depth=2

**3. Synchronization sequence matching**: A TPUSH must correspond to a TPOP + TFREE

**4. Error example**:
```cpp
// Error: TPUSH twice in succession, no corresponding TPOP
TPUSH(pipe, tile1);
TPUSH(pipe, tile2);  // ERROR

// Correct:
TPUSH(pipe, tile1);
// ... consumer core ...
TPOP(pipe, vecTile1);
TFREE(pipe);
// Then the next TPUSH can be performed
```

#### Inter-core synchronization in fusion operator

When the operator involves the alternate use of Vector calculation and Cube calculation, TPUSH/TPOP needs to be used at the switching point:

| Switch scene | Data flow | Direction | Inter-core synchronization |
|---------|-------|------|---------|
| Vector → Cube | UB → L1 | V2C | TPUSH (Vec) + TPOP (Cube) |
| Cube → Vector | L0C → UB | C2V | TPUSH (Cube) + TPOP (Vec) |

**Flash Attention inter-core synchronization example**:
- Phase 1 (Vector): K transpose → TPUSH K^T to Cube core (V2C)
- Phase 2 (Cube): QK matrix multiplication → TPUSH Score to Vector core (C2V)
- Phase 3 (Vector): Softmax normalization → TPUSH P to Cube core (V2C)
- Phase 4 (Cube): PV matrix multiplication → TSTORE output

Detailed reference: `/home/developer/.agents/skills/pto-isa-operator-implementation/TPUSH_TPOP_GUIDE.md`

## Example

### Example 1: ReLU activation function

**Operator function**: ReLU(x) = max(0, x)

**ISA instruction**: TLOAD → TRELU → TSTORE

**Kernel code**:
```cpp
namespace ReLU {

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
__global__ AICORE void runReLU(__gm__ T *out, __gm__ T *src)
{
    using DynShapeDim5 = Shape<1, 1, 1, vRows, vCols>;
    using DynStrideDim5 = Stride<1, 1, 1, vCols, 1>;
    using GlobalData = GlobalTensor<T, DynShapeDim5, DynStrideDim5>;
    using TileData = Tile<TileType::Vec, T, kTRows_, kTCols_, BLayout::RowMajor, -1, -1>;

    TileData srcTile(vRows, vCols);
    TileData dstTile(vRows, vCols);
    TASSIGN(srcTile, 0x0);
    TASSIGN(dstTile, sizeof(T) * TileData::Numel);

    GlobalData srcGlobal(src);
    GlobalData dstGlobal(out);

    Event<Op::TLOAD, Op::TRELU> event0;
    Event<Op::TRELU, Op::TSTORE_VEC> event1;

    event0 = TLOAD(srcTile, srcGlobal);
    event1 = TRELU(dstTile, srcTile, event0);
    TSTORE(dstGlobal, dstTile, event1);

    out = dstGlobal.data();
}

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
void launchReLU(T *out, T *src, void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16>) {
        runReLU<half, kTRows_, kTCols_, vRows, vCols>
            <<<1, nullptr, stream>>>((half *)out, (half *)src);
    } else {
        runReLU<T, kTRows_, kTCols_, vRows, vCols><<<1, nullptr, stream>>>(out, src);
    }
}

template void launchReLU<float, 64, 64, 64, 64>(float *out, float *src, void *stream);
template void launchReLU<aclFloat16, 16, 256, 16, 256>(aclFloat16 *out, aclFloat16 *src, void *stream);

} // namespace ReLU
```

### Example 2: Element-wise addition (TADD)

**Operator function**: dst = src0 + src1

**ISA instructions**: TLOAD → TLOAD → TADD → TSTORE

**Kernel code**:
```cpp
namespace TAdd {

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
__global__ AICORE void runTAdd(__gm__ T *out, __gm__ T *src0, __gm__ T *src1)
{
    using DynShapeDim5 = Shape<1, 1, 1, vRows, vCols>;
    using DynStrideDim5 = Stride<1, 1, 1, vCols, 1>;
    using GlobalData = GlobalTensor<T, DynShapeDim5, DynStrideDim5>;
    using TileData = Tile<TileType::Vec, T, kTRows_, kTCols_, BLayout::RowMajor, -1, -1>;

    TileData src0Tile(vRows, vCols);
    TileData src1Tile(vRows, vCols);
    TileData dstTile(vRows, vCols);
    TASSIGN(src0Tile, 0x0);
    TASSIGN(src1Tile, sizeof(T) * TileData::Numel);
    TASSIGN(dstTile, 2 * sizeof(T) * TileData::Numel);

    GlobalData src0Global(src0);
    GlobalData src1Global(src1);
    GlobalData dstGlobal(out);

    Event<Op::TLOAD, Op::TADD> event0;
    Event<Op::TADD, Op::TSTORE_VEC> event1;

    TLOAD(src0Tile, src0Global);
    event0 = TLOAD(src1Tile, src1Global);
    event1 = TADD(dstTile, src0Tile, src1Tile, event0);
    TSTORE(dstGlobal, dstTile, event1);

    out = dstGlobal.data();
}

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
void launchTAdd(T *out, T *src0, T *src1, void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16>) {
        runTAdd<half, kTRows_, kTCols_, vRows, vCols>
            <<<1, nullptr, stream>>>((half *)out, (half *)src0, (half *)src1);
    } else {
        runTAdd<T, kTRows_, kTCols_, vRows, vCols><<<1, nullptr, stream>>>(out, src0, src1);
    }
}

template void launchTAdd<float, 64, 64, 64, 64>(float *out, float *src0, float *src1, void *stream);
template void launchTAdd<aclFloat16, 16, 256, 16, 256>(aclFloat16 *out, aclFloat16 *src0, aclFloat16 *src1, void *stream);

} // namespace TAdd
```

### Example 3: Softmax normalization

**Operator function**: Softmax(x) = exp(x) / sum(exp(x))

**ISA instructions**: TLOAD → TEXP → TCOLSUM → TCOLEXPANDDIV → TSTORE

**Kernel code**:
```cpp
namespace Softmax {

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
__global__ AICORE void runSoftmax(__gm__ T *out, __gm__ T *src)
{
    using DynShapeDim5 = Shape<1, 1, 1, vRows, vCols>;
    using DynStrideDim5 = Stride<1, 1, 1, vCols, 1>;
    using GlobalData = GlobalTensor<T, DynShapeDim5, DynStrideDim5>;
    using TileData = Tile<TileType::Vec, T, kTRows_, kTCols_, BLayout::RowMajor, -1, -1>;
    using SumTileData = Tile<TileType::Vec, T, vRows, 1, BLayout::ColMajor, -1, -1>;

    TileData srcTile(vRows, vCols);
    TileData expTile(vRows, vCols);
    TileData dstTile(vRows, vCols);
    SumTileData sumTile(vRows, 1);
    
    TASSIGN(srcTile, 0x0);
    TASSIGN(expTile, sizeof(T) * TileData::Numel);
    TASSIGN(sumTile, 2 * sizeof(T) * TileData::Numel);
    TASSIGN(dstTile, 3 * sizeof(T) * TileData::Numel);

    GlobalData srcGlobal(src);
    GlobalData dstGlobal(out);

    Event<Op::TLOAD, Op::TEXP> event0;
    Event<Op::TEXP, Op::TCOLSUM> event1;
    Event<Op::TCOLSUM, Op::TCOLEXPANDDIV> event2;
    Event<Op::TCOLEXPANDDIV, Op::TSTORE_VEC> event3;

    event0 = TLOAD(srcTile, srcGlobal);
    event1 = TEXP(expTile, srcTile, event0);
    event2 = TCOLSUM(sumTile, expTile, event1);
    event3 = TCOLEXPANDDIV(dstTile, expTile, sumTile, event2);
    TSTORE(dstGlobal, dstTile, event3);

    out = dstGlobal.data();
}

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
void launchSoftmax(T *out, T *src, void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16>) {
        runSoftmax<half, kTRows_, kTCols_, vRows, vCols>
            <<<1, nullptr, stream>>>((half *)out, (half *)src);
    } else {
        runSoftmax<T, kTRows_, kTCols_, vRows, vCols><<<1, nullptr, stream>>>(out, src);
    }
}

template void launchSoftmax<float, 64, 64, 64, 64>(float *out, float *src, void *stream);
template void launchSoftmax<aclFloat16, 16, 256, 16, 256>(aclFloat16 *out, aclFloat16 *src, void *stream);

} // namespace Softmax
```

### Example 4: Batch Normalization

**Operator function**: BN(x) = (x - mean) / sqrt(var + eps) * gamma + beta

**ISA instructions**: TLOAD → TSUBS → TDIVS → TMULS → TADDS → TSTORE

**Kernel code**:
```cpp
namespace BatchNorm {

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
__global__ AICORE void runBatchNorm(__gm__ T *out, __gm__ T *src,
                                    float mean, float var, float eps, float gamma, float beta)
{
    using DynShapeDim5 = Shape<1, 1, 1, vRows, vCols>;
    using DynStrideDim5 = Stride<1, 1, 1, vCols, 1>;
    using GlobalData = GlobalTensor<T, DynShapeDim5, DynStrideDim5>;
    using TileData = Tile<TileType::Vec, T, kTRows_, kTCols_, BLayout::RowMajor, -1, -1>;

    TileData srcTile(vRows, vCols);
    TileData normTile(vRows, vCols);
    TileData dstTile(vRows, vCols);
    TASSIGN(srcTile, 0x0);
    TASSIGN(normTile, sizeof(T) * TileData::Numel);
    TASSIGN(dstTile, 2 * sizeof(T) * TileData::Numel);

    GlobalData srcGlobal(src);
    GlobalData dstGlobal(out);

    Event<Op::TLOAD, Op::TSUBS> event0;
    Event<Op::TSUBS, Op::TDIVS> event1;
    Event<Op::TDIVS, Op::TMULS> event2;
    Event<Op::TMULS, Op::TADDS> event3;
    Event<Op::TADDS, Op::TSTORE_VEC> event4;

    T std_val = (T)sqrt(var + eps);

    event0 = TLOAD(srcTile, srcGlobal);
    event1 = TSUBS(normTile, srcTile, (T)mean, event0);
    event2 = TDIVS(normTile, normTile, std_val, event1);
    event3 = TMULS(dstTile, normTile, (T)gamma, event2);
    event4 = TADDS(dstTile, dstTile, (T)beta, event3);
    TSTORE(dstGlobal, dstTile, event4);

    out = dstGlobal.data();
}

template <typename T, int kTRows_, int kTCols_, int vRows, int vCols>
void launchBatchNorm(T *out, T *src, float mean, float var, float eps, float gamma, float beta, void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16>) {
        runBatchNorm<half, kTRows_, kTCols_, vRows, vCols>
            <<<1, nullptr, stream>>>((half *)out, (half *)src, mean, var, eps, gamma, beta);
    } else {
        runBatchNorm<T, kTRows_, kTCols_, vRows, vCols><<<1, nullptr, stream>>>(out, src, mean, var, eps, gamma, beta);
    }
}

template void launchBatchNorm<float, 64, 64, 64, 64>(float *out, float *src, float mean, float var, float eps, float gamma, float beta, void *stream);
template void launchBatchNorm<aclFloat16, 16, 256, 16, 256>(aclFloat16 *out, aclFloat16 *src, float mean, float var, float eps, float gamma, float beta, void *stream);

} // namespace BatchNorm
```

### Example 5: Matrix Multiplication (TMATMUL) - Cube Core

**Operator function**: C = A * B (matrix multiplication)

**ISA instruction**: TLOAD → TMOV → TMATMUL → TSTORE (GM → L1 → L0 → L0C → GM)

**Important**: Matrix multiplication uses the Cube core, and you need to use the `DAV_CUBE` macro to determine the execution path.

**Kernel code**:
```cpp
namespace MatMul {

#ifdef __DAV_CUBE__
constexpr bool DAV_CUBE = true;
#else
constexpr bool DAV_CUBE = false;
#endif

template <typename T, typename U, typename S, int validM, int validK, int validN>
__global__ AICORE void runMatMul(__gm__ T *out, __gm__ U *src0, __gm__ S *src1)
{
    if constexpr (DAV_CUBE) {
        constexpr int blockAlign = C0_SIZE_BYTE / sizeof(U);
        constexpr int M = CeilAlign<int>(validM, 16);
        constexpr int N = CeilAlign<int>(validN, blockAlign);
        constexpr int K = CeilAlign<int>(validK, blockAlign);

        using GlobalDataSrc0 = GlobalTensor<U, pto::Shape<1, 1, 1, validM, validK>,
                                            pto::Stride<1 * validM * validK, 1 * validM * validK, validM * validK, validK, 1>>;
        using GlobalDataSrc1 = GlobalTensor<S, pto::Shape<1, 1, 1, validK, validN>,
                                            pto::Stride<1 * validK * validN, 1 * validK * validN, validK * validN, validN, 1>>;
        using GlobalDataOut = GlobalTensor<T, pto::Shape<1, 1, 1, validM, validN>,
                                           pto::Stride<1 * validM * validN, 1 * validM * validN, validM * validN, validN, 1>>;

        GlobalDataSrc0 src0Global(src0);
        GlobalDataSrc1 src1Global(src1);
        GlobalDataOut dstGlobal(out);

        using TileMatAData = Tile<TileType::Mat, U, M, K, BLayout::ColMajor, validM, validK, SLayout::RowMajor, 512>;
        using TileMatBData = Tile<TileType::Mat, S, K, N, BLayout::ColMajor, validK, validN, SLayout::RowMajor, 512>;
        using LeftTile = TileLeft<U, M, K, validM, validK>;
        using RightTile = TileRight<S, K, N, validK, validN>;
        using AccTile = TileAcc<T, M, N, validM, validN>;

        TileMatAData aMatTile;
        TileMatBData bMatTile;
        LeftTile aTile;
        RightTile bTile;
        AccTile cTile;

        TASSIGN(aMatTile, 0x0);
        TASSIGN(bMatTile, 0x20000);

        TLOAD(aMatTile, src0Global);
        TLOAD(bMatTile, src1Global);

#ifndef __PTO_AUTO__
        set_flag(PIPE_MTE2, PIPE_MTE1, EVENT_ID0);
        wait_flag(PIPE_MTE2, PIPE_MTE1, EVENT_ID0);
#endif

        TMOV(aTile, aMatTile);
        TMOV(bTile, bMatTile);

#ifndef __PTO_AUTO__
        set_flag(PIPE_MTE1, PIPE_M, EVENT_ID0);
        wait_flag(PIPE_MTE1, PIPE_M, EVENT_ID0);
#endif

        TMATMUL(cTile, aTile, bTile);

#ifndef __PTO_AUTO__
        set_flag(PIPE_M, PIPE_FIX, EVENT_ID0);
        wait_flag(PIPE_M, PIPE_FIX, EVENT_ID0);
#endif

        TSTORE(dstGlobal, cTile);
        out = dstGlobal.data();
    }
}

template <typename T, typename U, typename S, int validM, int validK, int validN>
void launchMatMul(T *out, U *src0, S *src1, void *stream)
{
    if constexpr (std::is_same_v<T, aclFloat16> || std::is_same_v<U, aclFloat16> || std::is_same_v<S, aclFloat16>) {
        runMatMul<half, half, half, validM, validK, validN>
            <<<1, nullptr, stream>>>((half *)out, (half *)src0, (half *)src1);
    } else {
        runMatMul<T, U, S, validM, validK, validN><<<1, nullptr, stream>>>(out, src0, src1);
    }
}

template void launchMatMul<float, float, float, 16, 16, 16>(float *out, float *src0, float *src1, void *stream);
template void launchMatMul<half, half, half, 16, 16, 16>(half *out, half *src0, half *src1, void *stream);

} // namespace MatMul
```

## Best Practices

### 1. ISA instruction selection principles

**Minimize the number of instructions**: Use the minimum number of instructions to complete the function and reduce data transfer overhead.

**Prefer using fusion instructions**: Choose fusion instructions to reduce intermediate steps:
- TAXPY (Fusion Multiply and Add) - Vector calculation
- TMATMUL_ACC (fused accumulation matrix multiplication) - Cube calculation
- TMATMUL_BIAS (fusion plus bias matrix multiplication) - Cube calculation
- TROWEXPANDADD (fusion broadcast addition) - Vector calculation
- TADDC/TSUBC (Fusion Ternary Operation) - Vector calculation

**Select the appropriate data flow**: Select the optimal data flow path based on the operator characteristics.
- **Vector calculation**: Use GM → UB → V → UB → GM data flow, suitable for element-by-element operations
- **Cube calculation**: using GM → L1 → L0A/L0B → L0C → GM data flow, suitable for matrix multiplication

### 2. Data flow optimization

**Vector calculation optimization**:
- Try to perform multiple calculations on UB
- Use in-place operations to reduce intermediate tiles
- Proper use of buffer reuse
- Avoid unnecessary TMOV operations

**Cube calculation optimization**:
- Properly plan L1 and L0 buffer sizes
- Conversion using TileType::Mat and TileType::Vec
- Optimize matrix blocking strategy
- Reduce the number of GM visits

**Alignment and Layout**:
- RowMajor: cols require 32-byte alignment
- ColMajor: rows require 32-byte alignment
- Use constexpr to calculate alignment dimensions

### 3. Synchronization strategy selection

**Event synchronization is recommended**:
- Automatic dependency tracking
- Compiler optimization friendly
- The code is concise and easy to maintain
- Supports manual and automatic modes

**Alternative Manual Sync**:
- Complex pipeline control
- Requires fine-grained synchronization
- Performance critical path optimization

### 4. Tile dimension selection

**Common Tile dimension configuration**:
| Data type | Recommended Tile dimensions |
|---------|-------------|
| float | 64x64, 32x32, 16x16 |
| aclFloat16 | 16x256, 8x768, 4x1024 |
| int32 | 64x64, 32x32 |
| int16 | 64x128, 32x256 |

### 5. Type processing

**aclFloat16 conversion**:
- API type: aclFloat16
- Hardware type: half
- Conversion in launch function

**Mixed Precision Support**:
- Support multiple types using template parameters
- Use float for scalar parameters uniformly

### 6. Code organization

**Naming convention**:
- Kernel file: `t<operation command>_kernel.cpp`
- Namespace: `OperatorName`
- Function name: `runOperator`, `launchOperator`

**Template instantiation**:
- Provide explicit instantiation for common configurations
- Reduce compilation time
- Make sure the code is linkable

## FAQ

### Q1: How to choose the appropriate ISA instruction combination?

**Answer**:
1. Analyze operator functions and decompose them into basic operations
2. Find the corresponding instructions in PTOISA.md
3. Arrange instructions in data flow order
4. Check the dependencies between instructions
5. Consider fusion instruction reduction steps

### Q2: What is the data flow sequence?

**Answer**:
PTO has two main data flow modes:

**1. Vector calculation data flow (element-by-element operation)**: gm → ub → vector → ub → gm
- **Phase 1**: GM → UB (TLOAD)
- **Phase 2/3**: Vector calculation (TADD/TMUL/TEXP, etc.)
- **Phase 5**: UB → GM (TSTORE)

**2. Cube calculation data flow (matrix multiplication)**: GM → L1 → L0A/L0B → L0C → GM
- **Phase 1**: GM → L1 (TLOAD)
- **Phase 2**: L1 → L0A/L0B (TMOV)
- **Phase 3**: Cube calculation (TMATMUL)
- **Phase 4**: L0C → GM (TSTORE)

**Key differences**:
- Vector calculations use UB buffers, suitable for element-by-element operations
- Cube calculations use L1 and L0 buffers, suitable for matrix multiplication

### Q3: When to use Event synchronization and when to use manual synchronization?

**Answer**:
- **Event synchronization (recommended)**: simple integration, clear dependencies, automatic mode support
- **Manual synchronization**: complex pipeline, fine-grained control, performance optimization

### Q4: How to deal with complex operators (such as GELU, LayerNorm)?

**Answer**:
1. Decompose complex operators into multiple basic operations
2. Select the corresponding ISA instruction for each basic operation
3. Reasonably arrange the intermediate Tile buffer
4. Optimize data flow and reduce handling
5. Consider using approximate calculations to simplify implementation

### Q5: How to choose Tile dimensions?

**Answer**:
- Select alignment dimensions based on data type
- Consider on-chip storage capacity limitations
- Balance computing efficiency and storage overhead
- Use constexpr to calculate alignment dimensions

### Q6: How to verify whether the ISA instruction selection is correct?

**Answer**:
1. Check whether the instruction function matches the operator requirements
2. Verify data flow integrity (GM → UB → GM)
3. Confirm that the synchronization mechanism is correctly set up
4. Test on CPU emulator
5. Compare and verify with golden results

### Q7: How to deal with scalar parameters?

**Answer**:
- Scalar parameters use float type uniformly
- Convert to Tile data type before instruction call: `(T)scalar`
- Use scalar instructions (TADDS/TMULS, etc.) instead of Tile instructions

### Q8: When to use Vector data flow and when to use Cube data flow?

**Answer**:
Choose the appropriate data stream based on the operator type:

**Use Vector data stream (GM → UB → V → UB → GM)**:
- Element-wise operations: TADD, TSUB, TMUL, TDIV, TMAX, TMIN
- Mathematical functions: TEXP, TLOG, TSQRT, TPOW
- Activation function: TRELU, TPRELU, TLRELU
- Scalar operations: TADDS, TMULS, TDIVS
- Axis reduction: TROWSUM, TCOLSUM, TROWMAX
- Broadcast operations: TROWEXPANDADD, TCOLEXPANDADD
- Type conversion: TCVT

**Using Cube data stream (GM → L1 → L0A/L0B → L0C → GM)**:
- Matrix multiplication: TMATMUL, TMATMUL_ACC, TMATMUL_BIAS
- Matrix vector multiplication: TGEMV, TGEMV_ACC, TGEMV_BIAS
- Requires matrix operations using TileType::Mat

**Judgment method**:
- If using TileType::Vec → Vector data stream
- If using TileType::Mat → Cube data stream

### Q9: What is the role of TMOV in matrix multiplication?

**Answer**:
TMOV is used for data handling in matrix multiplication:

**Data flow**: L1 → L0A/L0B

**Specific functions**:
- TLOAD loads matrix data into L1Buffer (MatTile)
- TMOV moves MatTile data to L0Buffer (LeftTile and RightTile)
- TMATMUL performs calculations in L0Buffer

**Why TMOV is needed**:
- L1Buffer and L0Buffer are different physical storage areas
- L1Buffer is used to store loaded raw data
- L0Buffer is the dedicated buffer (L0A/L0B) of the Cube computing unit
- TMOV transfers data from L1 to L0 and prepares for matrix multiplication calculations

### Q10: When is inter-core synchronization (TPUSH/TPOP) used?

**Answer**:
When the operator involves data transmission between the Vector core and Cube core, TPUSH/TPOP must be used:

**Usage Scenario**:
- The calculation results of the Vector core need to be passed to the Cube core for matrix multiplication
- Cube core matrix multiplication results need to be passed to the Vector core for element-by-element operations
- Vector/Cube are used alternately in the fusion operator

**Scenarios without using TPUSH/TPOP**:
- Data transfer within the same core uses TMOV
- Pure Vector calculation or pure Cube calculation does not require inter-core synchronization

## References

- **ISA Reference**: `pto-isa/docs/PTOISA.md` - PTO instruction index
- **ISA detailed documentation**: `pto-isa/docs/isa/` - Detailed description of each command
  - `docs/isa/TMATMUL.md` - Matrix multiplication instructions
  - `docs/isa/TLOAD.md` - data loading instructions
  - `docs/isa/TMOV.md` - Data transfer instructions
- **C++ API**: `include/pto/pto-inst.hpp` - PTO instruction C++ interface
- **Constant definition**: `include/pto/common/constants.hpp` - Pipeline, event ID and other constants
- **Test example**: `tests/npu/a2a3/src/st/testcase/` - Example of operator implementation
- **Fusion Operator Guide**: `vector-fusion-operator-generate` skill - Complete process of fusion operator development

## Summary

This skill provides a complete process for using PTO-ISA to implement the specified operator function:

1. **Step 1**: Read PTOISA.md to understand the instruction set
2. **Step 2**: Analyze operator requirements and list ISA instructions
3. **Step 3**: Explain the command function in the order of data flow
   - Vector calculation: GM → UB → V → UB → GM
   - Cube calculation: GM → L1 → L0A/L0B → L0C → GM
4. **Step 4**: Output the complete kernel code

By following this guide, developers can systematically select ISA instructions, understand the two data flow modes (Vector and Cube), and generate high-quality kernel code.

**Key Takeaways**:
- **Vector calculation**: Use UB buffer, suitable for element-by-element operation, pipeline MTE2 → V → MTE3
- **Cube Computation**: Using L1 and L0 buffers, suitable for matrix multiplication, pipeline MTE2 → MTE1 → M → FIX → MTE3
- **Key role of TMOV**: Move L1 data to L0 in matrix multiplication to prepare for Cube calculation
