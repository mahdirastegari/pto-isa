---
name: PTO-COMM Communication Operator Performance Optimization Guide
description: PTO-COMM communication operator performance optimization methodology and practical skills. Covers overlap, ping-pong double buffering, multi-block load balancing, synchronization overhead optimization, data layout optimization, Tile size selection, bandwidth utilization analysis, performance modeling and profiling methods, etc. Trigger: When it is necessary to optimize the performance of the PTO-COMM communication operator, analyze communication bottlenecks, improve bandwidth utilization, and design a general calculation overlap strategy.
license: CANN Open Software License Agreement Version 2.0
---

# PTO-COMM Communication Operator Performance Optimization Guide

## Positioning

This Skill is a **knowledge base + methodology** Skill that provides systematic methods, key techniques and analysis tools for PTO-COMM communication operator performance optimization.

---

## Performance optimization philosophy

### Core Principles

1. **Hide delay**: Hide communication delay in calculation (general calculation overlap)
2. **Maximize Bandwidth**: Keep hardware communication paths full (pipeline, bulk transfer)
3. **Eliminate Bottlenecks**: Identify and eliminate load imbalances and synchronization waits

### Performance upper bound

```
Total time ≥ max (computation time, communication time, synchronization overhead)

Communication time = data volume / link bandwidth
Calculation time = calculation amount / calculation peak value
Synchronization overhead = signal rounds × single synchronization delay
```

**Ideal state**: Communication is completely hidden in computation, total time ≈ computation time.

### Optimization priority

```
1. Algorithm selection (O(N) level impact)
   └── Ring vs Mesh vs built-in collective communication
2. Comprehensive overlapping strategy (2x+ level impact)
   └── Dual streams, queue scheduling, block granularity
3. Data transfer optimization (1.5x level impact)
   └── Ping-pong double buffering, Tile size, alignment
4. Synchronization optimization (1.1~1.3x level impact)
   └── barrier merging, signal compression, block role optimization
```

---

## Detailed explanation of each optimization dimension

| Dimensions | Detailed documentation |
|------|---------|
| Overlap design | [Detailed explanation of overlap](references/overlap-design.md) |
| Ping-pong double buffering and Tile selection | [Data transfer optimization](references/data-transfer-optimization.md) |
| Synchronization cost optimization and algorithm selection | [Synchronization and algorithm optimization](references/sync-algorithm-optimization.md) |
| Performance Modeling, Profiling and Iteration | [Performance Analysis Method](references/profiling-methodology.md) |

---

## Optimization Decision Quick Reference

### Scenario decision table

| Scenario | First Optimization | Reference |
|------|---------|------|
| Communication time > Computation time | Increase calculation granularity / reduce communication volume | overlap-design.md |
| Computation time > Communication time | Communication has been hidden, optimizing the computation itself | — |
| Overlap efficiency < 80% | Check block granularity, queue idling, Block balancing | overlap-design.md |
| Bandwidth utilization < 60% | Increase Tile, use ping-pong, check alignment | data-transfer-optimization.md |
| Multiple Barrier overhead is high | Merge RS+Reduce into AtomicAdd | sync-algorithm-optimization.md |
| Slow first run | Warmup excludes first time overhead | profiling-methodology.md |

### Overlap efficiency measure

```
Overlap efficiency = 1 - (actual total time - max(T_comp, T_comm)) / min(T_comp, T_comm)

100% = perfect overlap, total time = max(T_comp, T_comm)
  0% = no overlap, total time = T_comp + T_comm
```

---

## Optimization Checklist

### General calculation overlap

- [ ] Use different Streams for calculation and communication
- [ ] Join the queue as soon as the calculation is completed (without waiting for all completion)
- [ ] Communication kernel uses TTEST polling (non-TWAIT blocking)
- [ ] The block granularity is appropriate (communication has to be done before calculating the first Tile)
- [ ] measure and report overlap efficiency

### Data transfer

- [ ] Use pingpong double buffering for large numbers of small blocks
- [ ] Tile size makes full use of UB space
- [ ] GM data 32B alignment
- [ ] Asynchronous transmission uses one-dimensional continuous layout

### Synchronization optimization

- [ ] RS + Reduce merge into AtomicAdd (reduce one barrier)
- [ ] Cross-rank signals are only executed in block 0, other blocks and other local flags
- [ ] Avoid unnecessary pipe_barrier
- [ ] Use TTEST instead of dcci + software polling

### Load balancing

- [ ] AG stage uses row-level equalization
- [ ] RS stage queue is evenly distributed
- [ ] Block quantity matches hardware resources

### Algorithm level

- [ ] AllReduce is decomposed into RS + AG (eliminate root bottleneck)
- [ ] Use P2P composition instead of built-in collective communication when the data volume is large
- [ ] FP16 AtomicAdd has acceptable accuracy, otherwise it will be changed to independent Reduce

---

## Related Skills

| Skill | Purpose |
|-------|------|
| `pto-comm-isa-reference` | Command signature and constraint quick check |
| `pto-comm-operator-develop` | Communication operator development process |
| `pto-comm-testing-debug` | Testing and debugging methods |
| `vector-fusion-operator-generate` | Vector fusion operator development |
