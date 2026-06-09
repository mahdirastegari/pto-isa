---
name: PTO-COMM Communication Operator Development Guide
description: A complete guide to developing communication operators based on PTO-COMM ISA. Covers Host-Device architecture, file structure, communication mode (P2P/aggregated communication/general computing integration), synchronization strategy, signal matrix design, multi-block scheduling, remote address management, construction system configuration, etc. Trigger: When you need to use PTO-COMM to develop communication operators, design communication kernel, write Host-side code, and configure CMakeLists.
license: CANN Open Software License Agreement Version 2.0
---

# PTO-COMM Communication Operator Development Guide

## Positioning

This Skill is a **process Skill** that guides the development of a communication operator based on PTO-COMM ISA from scratch.

---

## Architecture Overview

### Host-Device separation

```
Host side Device side
┌─────────────────┐              ┌─────────────────────────┐
│ main.cpp        │              │ comm_kernel.cpp         │
│ - MPI initialization │ Startup │ - __global__ AICORE │
│ - ACL initialization │──kernel──→ │ - TPUT/TGET/TNOTIFY/... │
│ - HCCL communication domain │ │ - Signal synchronization logic │
│ - Memory Allocation │ ├──────────────────────────┤
│ - Kernel startup │ │ compute_kernel.cpp │
│ - Result Verification │ Startup │ - __global__ AICORE │
│                 │──kernel──→   │ - TMATMUL/TADD/...      │
└──────────────────┘ │ - Calculation logic │
                                 └─────────────────────────┘
```

**Key Principles**:
- **Host side**: Responsible for MPI/HCCL communication domain initialization, memory allocation, remote address acquisition, kernel startup and result verification
- **Device side**: Use the PTO-COMM instruction to perform the actual data transfer and synchronization
- Computation and communication can be compiled into separate `.so` files

---

## Programming model selection

```
Need inter-NPU communication?
├── Only basic P2P transfer required
│ └── Use TPUT/TGET → Refer to P2P mode in "Development Mode"
│
├── Requires collective communication (AllReduce/AllGather/ReduceScatter, etc.)
│ ├── Can this be done using the built-in set command?
│ │ └── Use TGATHER/TSCATTER/TBROADCAST/TREDUCE → Refer to the collective communication mode of "Development Mode"
│ └── Need a custom algorithm (such as RS+AG combination AllReduce)?
│ └── Use TPUT<AtomicAdd> + TNOTIFY/TWAIT combination → Refer to "Development Mode" for custom collective communication
│
├── Requires comprehensive computing fusion (computing + communication overlap)
│ └── Use dual kernel (cube + vec) + queue/signal synchronization → Refer to the general computing fusion mode of "Development Mode"
│
└── Requires asynchronous bulk transfer
    └── Use TPUT_ASYNC/TGET_ASYNC → refer to pto-comm-isa-reference
```

---

## File structure and naming convention

```
kernels/manual/<platform>/<operator_name>/
├── comm_kernel.cpp # Communication kernel (Vec architecture)
├── compute_kernel.cpp # Compute kernel (Cube architecture, if integration is required)
├── config.h # Tiling configuration, Block number, constant definition
├── kernel_launchers.h # Host side kernel startup function declaration
├── common.hpp # Sharing tools such as remote address calculation
├── main.cpp # Host side: initialization, startup, verification
├── CMakeLists.txt # Build configuration
├── run.sh # Run script
└── README_zh.md # Operator document
```

---

## Core development model

For complete code examples and synchronization strategies for the four development modes, see:

**Detailed Guide**: [Detailed explanation of development patterns](references/development-patterns.md)

| Mode | Command combination | Applicable scenarios |
|------|---------|---------|
| P2P | TPUT/TGET | Data transmission between two NPUs |
| Collective communication | TGATHER/TSCATTER/TBROADCAST/TREDUCE | Standard multi-rank operations |
| Customized collection communication | TPUT\<AtomicAdd\> + TNOTIFY/TWAIT | RS+AG combination to implement AllReduce |
| General computing fusion | Dual kernel + queue + signal matrix | Computation and communication overlap |

---

## Synchronization strategy and signal design

For details on signal matrix layout, DeviceBarrier implementation, and pipeline synchronization, see:

**Detailed Guide**: [Signal and Synchronization Design](references/signal-design.md)

### Quick Reference

| Synchronization requirements | Recommended methods |
|---------|---------|
| Cross-rank barrier | DeviceBarrier (Intra-rank + Cross-rank + local broadcast) |
| Separation between stages | `pipe_barrier(PIPE_ALL)` |
| Compute → Communication Notification | SPSC Ready Queue + TTEST Polling |
| Manual pipeline | `set_flag`/`wait_flag` (only required for TLOAD/TSTORE_IMPL) |
| Multiple parties notify one party | `NotifyOp::AtomicAdd` |
| One party notifies multiple parties | `NotifyOp::Set` |

---

## Remote address management and multi-block scheduling

For details on the remote address acquisition method, address alignment requirements, Block allocation strategy, and work equalization method, please see:

**Detailed Guide**: [Multi-Block Scheduling and Address Management](references/multi-block-scheduling.md)

### Address alignment requirements

- All GM addresses must meet 32-byte alignment
- Signal address must be 4-byte aligned
- The workspace of TPUT_ASYNC/TGET_ASYNC is managed by a dedicated Manager

### Multi-core sharding strategy

| Dimension segmentation | Applicable scenarios | Methods |
|---------|---------|------|
| Tile dimension | Large communication volume, large number of Tiles | Evenly distribute Tiles to each block |
| Row dimension | Requires precise load balancing | Flatten to row-level distribution (recommended) |
| Rank dimension | Different ranks are transmitted independently | Assigned to different blocks according to rank |

---

## Host side and build system

For details on the host side standard initialization process, CMakeLists template, SOC_VERSION mapping, and kernel startup mode:

**Detailed Guide**: [Host Side and Build System](references/host-build-system.md)

### SOC_VERSION and schema mapping

| SOC_VERSION | Architecture | Cube Arch | Vec Arch |
|-------------|------|-----------|----------|
| Ascend910B | A2A3 | dav-c220-cube | dav-c220-vec |
| Ascend910C | A2A3 | dav-c220-cube | dav-c220-vec |
| Ascend950 | A5 | dav-c350-cube | dav-c350-vec |

---

## Development Checklist

### Before development

- [ ] Confirm the target platform (A2A3/A5) and corresponding architecture compilation options
- [ ] Confirm communication topology (intra-node/across nodes) and link type
- [ ] Determine the communication mode (P2P/aggregation/fusion)
- [ ] Plan signal matrix layout

### Under implementation

- [ ] TNOTIFY target address is remote, TWAIT/TTEST listening address is local
- [ ] UB offsets of Ping Pong Tile do not overlap
- [ ] Use `pipe_barrier(PIPE_ALL)` to separate different stages
- [ ] Manual TLOAD/TSTORE_IMPL with correct set_flag/wait_flag
- [ ] All ranks use the same rootIdx to build ParallelGroup
- [ ] Non-root rank does not call the collective communication command
- [ ] The remote address is calculated correctly (based on the communication window offset)

### Before testing

- [ ] The signal matrix is cleared before each run.
- [ ] Host side `aclrtSynchronizeStream` ensures that kernel execution is completed
- [ ] Memory size is consistent with Tile configuration
- [ ] Vec/Cube architecture is selected correctly in CMakeLists

---

## Related Skills

| Skill | Purpose |
|-------|------|
| `pto-comm-isa-reference` | PTO-COMM command signature, parameters, constraints quick check |
| `pto-comm-testing-debug` | Communication operator testing and debugging guide |
| `pto-comm-performance-optimization` | Communication operator performance optimization |
| `vector-fusion-operator-generate` | PTO vector fusion operator development guide |
