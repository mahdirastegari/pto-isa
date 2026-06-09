# Detailed explanation of Overlap

## Basic principles

Deploy computation and communication on different hardware resources for parallel execution:
- **Calculation**: Cube kernel (matrix operations) or Vec kernel (vector operations)
- **Communication**: MTE engine (GM→UB→GM) or DMA engine (GM→GM)

```
time →

No overlap:
[── Compute ──][── Comm ──]  Total = T_comp + T_comm

There is overlap:
[── Compute ──────────────]
    [── Comm ─────────]     Total ≈ max(T_comp, T_comm)
```

---

## Implementation mode: dual Stream + queue scheduling

```
computeStream (Cube blocks):
  ┌────┐  ┌────┐  ┌────┐
  │Tile│→│Tile│→│Tile│→ ...
  │ 0  │  │ 1  │  │ 2  │
  └──┬─┘  └──┬─┘  └──┬─┘
     │       │       │
   enqueue enqueue enqueue ← Join the queue after calculation is completed
     │       │       │
     ▼       ▼       ▼
commStream (Vec blocks):
  poll → TPUT → poll → TPUT → ... ← Start transmission immediately
```

**Key Design Elements**:

1. **Ready Queue**: One SPSC queue for each calculation block, lock-free design
2. **Transmit when calculation is completed**: Do not wait for all tile calculations to be completed
3. **TTEST polling**: The communication kernel uses hardware instructions to poll the queue

---

## Overlap efficiency measure

```
Overlap efficiency = 1 - (actual total time - max(T_comp, T_comm)) / min(T_comp, T_comm)
```

- **100%**: perfect overlap, total time = max(T_comp, T_comm)
- **0%**: no overlap, total time = T_comp + T_comm

### Calculation method

```cpp
float pipe_total_us = MeasurePipelined();
float comp_only_us = MeasureComputeOnly();
float comm_est_us = pipe_total_us - comp_only_us;
float speedup = (comp_only_us + comm_est_us) / pipe_total_us;
printf("Overlap speedup: %.2fx\n", speedup);
```

---

## Block granularity selection

| Granularity | Advantages | Disadvantages |
|------|------|------|
| Fine-grained (small Tile) | Start communication earlier, better overlap | High synchronization overhead, complex queue management |
| Coarse-grained (large Tile) | Less synchronization, high transmission efficiency | Communication is idle before calculation is completed |

**Recommended**: Choose a maximum tile size such that communication start time < first tile calculation completion time.

---

## Multi-Block Load Balancing

When multiple blocks are run in parallel, if the work is unevenly distributed, the slowest block determines the total time.

### Row-level equal distribution (recommended)

```cpp
int total_rows = tile_count * ROWS_PER_TILE * (nranks - 1);
int rows_per_block = (total_rows + num_blocks - 1) / num_blocks;
int my_start = block_idx * rows_per_block;
int my_end = min((block_idx + 1) * rows_per_block, total_rows);

while (cur_row < my_end) {
    int flat_transfer = cur_row / ROWS_PER_TILE;
    int row_in_tile = cur_row % ROWS_PER_TILE;
    AgTransferRows(reduced_output, ctx, stride, remote_rank, row_offset, nrows);
    cur_row += nrows;
}
```

### Block quantity selection

| Factors | Impact |
|------|------|
| Number of AICore | Number of Blocks ≤ Number of available AICore |
| Data volume | Too little data is not worth more Blocks |
| Synchronization overhead | The more blocks there are, the more expensive intra-rank synchronization in the barrier is |
| Communication bandwidth | Multiple blocks may compete for the same link |

**Experience Value**:
- Communication kernel: 4~24 blocks
- Computing kernel: 24 blocks (full Cube core)
