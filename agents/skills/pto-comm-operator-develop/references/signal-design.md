# Signal and synchronization design

## Signal matrix layout

Communication operators usually require a signaling matrix to coordinate multi-rank synchronization. Typical layout:

```
Signal matrix (one copy for each rank, stored in the communication window/symmetric memory):
┌──────────────────────────────────────────────────────┐
│[0..MAX_RANKS-1] Cross-rank stage counter (RS/AG done)│
│ [MAX_RANKS] Local broadcast flag (block 0 → all) │
│ [MAX_RANKS+1] intra-rank block arrival counter │
│ ...(expand more stages on demand) │
└──────────────────────────────────────────────────────┘
```

**Design Principles**:
- Each phase uses an independent signal area to avoid signal reuse leading to competition
- Use `NotifyOp::AtomicAdd` to implement counting synchronization (multiple parties notify one party)
- Use `NotifyOp::Set` to implement flag synchronization (one party notifies multiple parties)

---

## Cross Rank Barrier mode

```cpp
AICORE inline void DeviceBarrier(__gm__ DeviceContext *ctx, __gm__ int32_t *signal_base,
                                 int phase, int my_rank, int nranks,
                                 int block_idx, int num_comm_blocks)
{
    // Step 1: Intra-rank barrier (all blocks must arrive)
    __gm__ int32_t *intra_counter = signal_base + INTRA_RANK_OFFSET + phase;
    if (block_idx != 0) {
        comm::Signal arrSig(intra_counter);
        comm::TNOTIFY(arrSig, 1, comm::NotifyOp::AtomicAdd);
    } else {
        if (num_comm_blocks > 1) {
            comm::Signal arrSig(intra_counter);
            comm::TWAIT(arrSig, num_comm_blocks - 1, comm::WaitCmp::GE);
        }
    }
    pipe_barrier(PIPE_ALL);

    // Step 2: Cross-rank barrier (only executed in block 0)
    if (block_idx == 0) {
        for (int r = 0; r < nranks; r++) {
            if (r == my_rank) continue;
            __gm__ int32_t *remote_sig = GetRemotePtr(ctx, signal_base + my_rank, r);
            comm::Signal sig(remote_sig);
            comm::TNOTIFY(sig, 1, comm::NotifyOp::AtomicAdd);
        }
        for (int r = 0; r < nranks; r++) {
            if (r == my_rank) continue;
            comm::Signal sig(signal_base + r);
            comm::TWAIT(sig, 1, comm::WaitCmp::GE);
        }
        __gm__ int32_t *local_flag = signal_base + LOCAL_FLAG_OFFSET + phase;
        comm::Signal localSig(local_flag);
        comm::TNOTIFY(localSig, 1, comm::NotifyOp::Set);
    } else {
        __gm__ int32_t *local_flag = signal_base + LOCAL_FLAG_OFFSET + phase;
        comm::Signal localSig(local_flag);
        comm::TWAIT(localSig, 1, comm::WaitCmp::GE);
    }
    pipe_barrier(PIPE_ALL);
}
```

---

## Intra-kernel synchronization mode

Different stages within the communication kernel are separated by `pipe_barrier(PIPE_ALL)`:

```cpp
// Phase 1: ReduceScatter
ReduceScatterPhase(...);
pipe_barrier(PIPE_ALL);

// Phase 2: Crossing rank barrier
DeviceBarrier(...);

// Stage 3: AllGather
AllGatherPhase(...);
pipe_barrier(PIPE_ALL);
```

---

## Manual pipeline synchronization

When using low-level `TLOAD`/`TSTORE_IMPL` instead of high-level `TPUT`/`TGET`, pipeline synchronization needs to be managed manually:

```cpp
TLOAD(tile, srcG);
set_flag(PIPE_MTE2, PIPE_MTE3, EVENT_ID0);
wait_flag(PIPE_MTE2, PIPE_MTE3, EVENT_ID0);
TSTORE_IMPL<TileData, Global, AtomicType::AtomicNone>(dstG, tile);
set_flag(PIPE_MTE3, PIPE_MTE2, EVENT_ID0);
wait_flag(PIPE_MTE3, PIPE_MTE2, EVENT_ID0);
```

**Note**: TPUT/TGET has internally handled pipeline synchronization, and there is no need to manually set_flag/wait_flag when used directly. Only required when building a custom pipeline using the underlying `TLOAD`/`TSTORE_IMPL`.
