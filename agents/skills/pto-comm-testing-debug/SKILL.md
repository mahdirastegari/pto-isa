---
name: PTO-COMM Communication Operator Testing and Debugging Guide
description: Testing methods and debugging techniques for PTO-COMM communication operator. Covers CPU simulation testing, NPU hardware testing, Golden data generation, correctness verification, multi-rank testing framework, common runtime error diagnosis, signal deadlock troubleshooting, accuracy problem analysis, mssanitizer memory detection, etc. Trigger: When it is necessary to test the PTO-COMM communication operator, generate Golden data, troubleshoot communication deadlocks/data errors/signal exceptions, and write test cases.
license: CANN Open Software License Agreement Version 2.0
---

# PTO-COMM Communication Operator Testing and Debugging Guide

## Positioning

This Skill is a **process + diagnostic** Skill, covering the complete testing process and common problem debugging methods of the PTO-COMM communication operator.

---

## Test system overview

### Test level

| Level | Purpose | Environment | Speed |
|------|------|------|------|
| CPU simulation | Function verification, fast iteration | x86_64 / AArch64 | Second level |
| Single instruction ST | Verify a single communication instruction | NPU hardware | Minute level |
| Operator level ST | Verify complete communication operator | Multi-NPU hardware | Minute level |
| Performance Test | Bandwidth/Latency/Throughput | Multi-NPU Hardware | Minute Level |

### Test directory structure

```
tests/
├── cpu/comm/st/testcase/ # CPU simulation test
│   ├── common.hpp
│   ├── CMakeLists.txt
│   ├── tgather/
│   └── tscatter/
├── npu/a2a3/comm/st/testcase/ # NPU A2A3 test
│   ├── common.hpp
│   ├── hccl_context.h
│   ├── comm_mpi.h
│   ├── CMakeLists.txt
│   ├── tput/ tget/ tnotify/ twait/ ttest/
│   ├── tgather/ tscatter/ tbroadcast/ treduce/
│   └── tput_async/ tget_async/
└── npu/a5/comm/st/testcase/ # NPU A5 test
```

---

## Detailed explanation of each test dimension

| Dimensions | Detailed documentation |
|------|---------|
| CPU simulation and NPU hardware testing | [Test environment and operation](references/test-environments.md) |
| Golden data generation and correctness verification | [Correctness verification method](references/correctness-verification.md) |
| Common problem diagnosis and debugging tools | [Problem Diagnosis Manual](references/troubleshooting-guide.md) |
| mssanitizer memory detection and advanced debugging | [Advanced debugging tools](references/advanced-debug-tools.md) |

---

## Quick diagnostic form

| Symptoms | Possible causes | First things to check |
|------|---------|--------|
| Program hang/timeout | TWAIT/TNOTIFY mismatch, barrier asymmetry | Signal direction, block number consistency |
| All zero output | Transfer not executed, address error | Remote address calculation, kernel started or not |
| Random value output | Read into uninitialized memory | Signal synchronization, write first, then read sequence |
| Partially correct | Tiling boundary problem | AlignUp, Tile boundary processing |
| NaN/Inf | FP16 overflow | AtomicAdd cumulative count |
| Close but not exact | FP16 precision limits | Relax atol/rtol |
| Abnormality in the second run | Signal residue | Clear the signal matrix before each run |
| Read stale data | Cache consistency | `dcci` + compiler barrier |

---

## Step-by-step troubleshooting method

```
1. CPU simulation verification data logic → passed
2. Single rank single block verification → passed
3. Single-rank multi-block verification → Troubleshoot intra-rank synchronization
4. 2 rank verification → troubleshoot cross-rank synchronization
5. 8 rank verification → troubleshooting scaling issues
```

---

## Accuracy Standard Quick Check

| Data type | Recommend atol | Recommend rtol | Description |
|---------|----------|----------|------|
| float (FP32) | 1e-5 | 1e-4 | High precision |
| half (FP16) | 1.0 | 0.01 | AtomicAdd has a large cumulative error |
| int32 / int16 | 0 | 0 | exact match |

---

## Test Checklist

### Functional testing

- [ ] CPU simulation passed (verify data logic)
- [ ] single rank/single block pass
- [ ] Single rank/multi-block pass (intra-rank synchronization)
- [ ] 2 rank passed (basic cross-rank communication)
- [ ] 8 rank (or target scale) passed
- [ ] The signal matrix is cleared before each run.
- [ ] FP16 accuracy within atol/rtol thresholds

### Boundary testing

- [ ] Data dimension non-alignment (padding required)
- [ ] Small amount of data that can be accommodated by a single Tile
- [ ] Very large data volume (automatic chunking)
- [ ] nranks = 2 (minimum multiple ranks)
- [ ] nranks = 8 (typical scale)

### Robustness test

- [ ] Passed multiple consecutive runs (excluding signal residue)
- [ ] Different data patterns (all zeros, all ones, random, extreme values)
- [ ] Different Block configurations (1/4/8/24 blocks)

### Performance testing

- [ ] Warmup post-stabilization performance data
- [ ] Compute-only baseline comparison
- [ ] Pipeline overlap efficiency (pipelined / (compute + comm))
- [ ] Bandwidth utilization (actual/theoretical peak)

---

## Related Skills

| Skill | Purpose |
|-------|------|
| `pto-comm-isa-reference` | Command signature and constraint quick check |
| `pto-comm-operator-develop` | Communication operator development process |
| `pto-comm-performance-optimization` | Performance optimization methods |
| `vector-fusion-operator-generate` | Vector fusion operator development and testing |
