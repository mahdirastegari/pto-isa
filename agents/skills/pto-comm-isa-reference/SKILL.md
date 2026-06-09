---
name: PTO-COMM ISA Command Quick Reference Manual
description: PTO communication command set complete reference manual. Covers signatures, parameters, constraints, data flows, and usage examples for all 12 communication instructions (TPUT/TGET/TNOTIFY/TWAIT/TTEST/TGATHER/TSCATTER/TBROADCAST/TREDUCE/TPUT_ASYNC/TGET_ASYNC and BuildAsyncSession). Triggered: When querying the usage of PTO communication instructions, parameter meanings, constraints, signal types, ParallelGroup usage, and AsyncSession construction methods.
license: CANN Open Software License Agreement Version 2.0
---

# PTO-COMM ISA Command Quick Reference Manual

## Positioning

This Skill is a **knowledge base** quick reference manual that provides a quick index of all PTO-COMM communication instructions. Each instruction is organized into categories and contains signatures, parameter descriptions, and key constraints.

---

## Header files and namespaces

```cpp
#include <pto/comm/pto_comm_inst.hpp> // Unified public API, only this one header file is needed
#include <pto/pto-inst.hpp> // PTO core instructions (TLOAD/TSTORE, etc.)

using namespace pto;
using namespace pto::comm;
```

`pto_comm_inst.hpp` is automatically distributed to the NPU native implementation or the CPU emulation backend based on the compilation macros.

---

## Overview of command categories

| Category | Command | Description |
|------|------|------|
| Peer-to-peer (synchronous) | `TPUT`, `TGET` | Remote write/read via UB staging Tile, supports single buffering and ping-pong double buffering |
| Signal synchronization | `TNOTIFY`, `TWAIT`, `TTEST` | Flag-based cross-NPU synchronization, signal is `int32_t` scalar or 2D grid |
| Set communication | `TGATHER`, `TSCATTER`, `TBROADCAST`, `TREDUCE` | Multi-rank operation based on `ParallelGroup`, initiated by root |
| Asynchronous communication | `TPUT_ASYNC`, `TGET_ASYNC` | GM→GM DMA transfer through SDMA/URMA engine, returning `AsyncEvent` |

### Data flow model

```
Synchronous point-to-point (TPUT/TGET):
  Local GM → UB Tile (temporary storage) → remote GM

Asynchronous point-to-point (TPUT_ASYNC/TGET_ASYNC):
  Local GM → DMA engine (SDMA/URMA) → remote GM (without going through UB)

Collective communication (TGATHER/TSCATTER/TBROADCAST/TREDUCE):
  Multi-rank GM → UB Tile (temporary storage) → local GM (automatic two-dimensional tile sliding)
```

---

## Instruction selection decision tree

```
Need to transfer data between NPUs?
├── One-to-one transmission
│ ├── Requires UB intermediate temporary storage (Tile level operation) → TPUT / TGET
│ │ ├── Write to remote → TPUT (supports AtomicAdd)
│ │ └── Read from remote → TGET (atomic operation not supported)
│ └── Large block GM → GM direct transmission (without UB) → TPUT_ASYNC / TGET_ASYNC
│ ├── SDMA Engine (Universal) → DmaEngine::SDMA
│ └── URMA Engine (A5 only) → DmaEngine::URMA
│
├──Multi-rank operations
│ ├── Collect → TGATHER
│ ├── Distribution → TSCATTER
│ ├── Broadcasting → TBROADCAST
│ └── Reduce → TREDUCE
│
└── Sync only (no data transfer)
    ├── Blocking wait → TWAIT
    ├── Non-blocking test → TTEST
    └── Send notification → TNOTIFY
```

---

## Core type quick check

| Type | Purpose | Key Constraints |
|------|------|---------|
| `Signal` | Scalar synchronization signal | `int32_t`, 4-byte aligned |
| `Signal2D<R,C>` | 2D signal grid | Compile time shape, supports sub-region view |
| `ParallelGroup<G>` | Collection communication group | External array view, all ranks must pass the same `rootIdx` |
| `NotifyOp` | Notification operation type | `AtomicAdd` (atomic addition) / `Set` (direct assignment) |
| `WaitCmp` | Comparison operators | EQ / NE / GT / GE / LT / LE |
| `ReduceOp` | Reduction operator | Sum / Max / Min |
| `AtomicType` | Atomic operation type | `AtomicNone` (default) / `AtomicAdd` |
| `DmaEngine` | DMA engine selection | `SDMA` (general) / `URMA` (A5 only) |
| `AsyncEvent` | Asynchronous event handler | `Wait` uses Quiet semantics (wait for all pending) |
| `AsyncSession` | Asynchronous session | Built by `BuildAsyncSession` |

**Detailed description**: [Detailed explanation of core types](references/core-types.md)

---

## Command constraint cheat sheet

| Command | Source Address | Destination Address | Requires UB Tile | Atomic Operation | Supports Ping-Pong | Return Type |
|------|--------|---------|-------------|---------|---------------|---------|
| TPUT | Local | Remote | Yes | AtomicNone/AtomicAdd | Yes | RecordEvent |
| TGET | Remote | Local | Yes | Not supported | Yes | RecordEvent |
| TNOTIFY | — | Remote | No | Set/AtomicAdd | No | void |
| TWAIT | local | — | no | — | no | void |
| TTEST | local | — | no | — | no | bool |
| TGATHER | Remote(Multiple) | Local | Yes | — | Yes | RecordEvent |
| TSCATTER | local | remote(multiple) | yes | — | yes | RecordEvent |
| TBROADCAST | local | remote(multiple) | yes | — | yes | RecordEvent |
| TREDUCE | Remote (multiple) | Local | Yes (2~3) | — | Yes | RecordEvent |
| TPUT_ASYNC | Local | Remote | No (requires scratch) | — | No | AsyncEvent |
| TGET_ASYNC | Remote | Local | No (scratch required) | — | No | AsyncEvent |

---

## Detailed explanation of various instructions

| Category | Detailed Documentation |
|------|---------|
| TPUT / TGET (synchronous P2P) | [Detailed explanation of P2P instructions](references/p2p-instructions.md) |
| TNOTIFY / TWAIT / TTEST (signal synchronization) | [Detailed explanation of signal synchronization instructions](references/signal-instructions.md) |
| TGATHER / TSCATTER / TBROADCAST / TREDUCE (collective communication) | [Detailed explanation of collective communication instructions](references/collective-instructions.md) |
| TPUT_ASYNC / TGET_ASYNC / BuildAsyncSession (asynchronous communication) | [Detailed explanation of asynchronous communication instructions](references/async-instructions.md) |

---

## Common Errors Quick Check

| # | Error | Rules |
|---|------|------|
| 1 | TNOTIFY to local/TWAIT and other remote | TNOTIFY → remote, TWAIT/TTEST → local |
| 2 | Non-root call collective communication | Only root execution, non-root may not call |
| 3 | Ping Pong Tile UB address overlap | pingTile and pongTile use different TASSIGN offsets |
| 4 | Asynchronous transmission uses non-one-dimensional tensor | TPUT_ASYNC/TGET_ASYNC only supports flat continuous one-dimensional |
| 5 | Signal type is not int32_t | Signal/Signal2D element type must be `int32_t` |
| 6 | ParallelGroup tensors are not initialized | The remote address must be set correctly |

---

## Related Skills

| Skill | Purpose |
|-------|------|
| `pto-comm-operator-develop` | The complete process of developing communication operators based on PTO-COMM |
| `pto-comm-testing-debug` | Communication operator testing and debugging guide |
| `pto-comm-performance-optimization` | Communication operator performance optimization |
| `vector-fusion-operator-generate` | PTO vector fusion operator development guide |
