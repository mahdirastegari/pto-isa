# Detailed explanation of development mode

## Mode 1: P2P communication

The most basic mode uses TPUT/TGET to transfer data between two NPUs.

```cpp
#include <pto/comm/pto_comm_inst.hpp>
#include <pto/pto-inst.hpp>

using namespace pto;

__global__ AICORE void P2PSendKernel(__gm__ half *local_data, __gm__ half *remote_addr)
{
    using ShapeDyn = Shape<DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC>;
    using StrideDyn = Stride<DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC>;
    using Global = GlobalTensor<half, ShapeDyn, StrideDyn, Layout::ND>;
    using TileData = Tile<TileType::Vec, half, 128, 256, BLayout::RowMajor, -1, -1>;

    ShapeDyn shape(1, 1, 1, 128, 256);
    StrideDyn stride(128 * 256, 128 * 256, 128 * 256, 256, 1);

    Global srcG(local_data, shape, stride);
    Global dstG(remote_addr, shape, stride);

    TileData stagingTile(128, 256);
    TASSIGN(stagingTile, 0x0);

    comm::TPUT(dstG, srcG, stagingTile);
}
```

---

## Mode 2: Collective communication

Use built-in collective communication instructions (suitable for standard scenarios).

```cpp
template <typename T, int NRANKS>
__global__ AICORE void ReduceKernel(__gm__ T *group_ptrs[NRANKS], __gm__ T *result, int my_rank)
{
    using TileT = Tile<TileType::Vec, T, 1, 1024>;
    using GTensor = GlobalTensor<T, Shape<1,1,1,1,1024>,
                                 Stride<1024,1024,1024,1024,1>, Layout::ND>;

    GTensor tensors[NRANKS];
    for (int i = 0; i < NRANKS; ++i) tensors[i] = GTensor(group_ptrs[i]);

    comm::ParallelGroup<GTensor> group(tensors, NRANKS, my_rank);
    GTensor dstG(result);
    TileT accTile, recvTile;
    comm::TREDUCE(group, dstG, accTile, recvTile, comm::ReduceOp::Sum);
}
```

---

## Mode 3: Custom collective communication (TPUT + TNOTIFY/TWAIT)

When the built-in set communication instructions do not meet the needs (such as the ReduceScatter + AllGather combination to implement AllReduce), use the underlying instruction combination.

### Method A: Use TPUT\<AtomicAdd\> (recommended, complete RS + Reduce in one step)

Each rank accumulates its own data directly to the output buffer of the owner rank through `TPUT<AtomicAdd>`, without the need for an independent Reduce stage.

```cpp
// ReduceScatter: Use TPUT<AtomicAdd> to directly accumulate to owner
AICORE inline void ReduceScatterViaTput(__gm__ half *local_src, __gm__ half *remote_dst,
                                        TileData &pingTile, TileData &pongTile)
{
    Global srcG(local_src, shape, stride);
    Global dstG(remote_dst, shape, stride);

    // TPUT<AtomicAdd> automatically handles pipeline synchronization and internal block sliding
    comm::TPUT<AtomicType::AtomicAdd>(dstG, srcG, pingTile, pongTile);
}

// AllGather: Use TPUT<AtomicNone> to write directly to the remote end
AICORE inline void AllGatherViaTput(__gm__ half *local_src, __gm__ half *remote_dst,
                                    TileData &pingTile, TileData &pongTile)
{
    Global srcG(local_src, shape, stride);
    Global dstG(remote_dst, shape, stride);

    comm::TPUT(dstG, srcG, pingTile, pongTile);
}
```

### Method B: Use TLOAD/TSTORE_IMPL (lower level, manual pipeline synchronization is required)

`set_flag`/`wait_flag` needs to be manually inserted between TLOAD and TSTORE_IMPL for pipeline synchronization. Suitable for scenarios where custom logic needs to be inserted between transmissions.

```cpp
// ReduceScatter: manual pipeline + AtomicAdd
AICORE inline void ReduceScatterManual(__gm__ half *src_addr, __gm__ half *dst_addr,
                                       TileData &pingTile, TileData &pongTile, int pp_count)
{
    bool use_ping = (pp_count % 2 == 0);
    TileData &curTile = use_ping ? pingTile : pongTile;
    event_t curEv = use_ping ? EVENT_ID0 : EVENT_ID1;

    Global srcG(src_addr, shape, stride);
    Global dstG(dst_addr, shape, stride);

    TLOAD(curTile, srcG);
    set_flag(PIPE_MTE2, PIPE_MTE3, curEv);
    wait_flag(PIPE_MTE2, PIPE_MTE3, curEv);
    TSTORE_IMPL<TileData, Global, AtomicType::AtomicAdd>(dstG, curTile);
    set_flag(PIPE_MTE3, PIPE_MTE2, curEv);
    wait_flag(PIPE_MTE3, PIPE_MTE2, curEv);
}

// AllGather: manual pipeline + normal write
AICORE inline void AllGatherManual(__gm__ half *src_addr, __gm__ half *dst_addr,
                                   TileData &tile)
{
    Global srcG(src_addr, shape, stride);
    Global dstG(dst_addr, shape, stride);

    TLOAD(tile, srcG);
    set_flag(PIPE_MTE2, PIPE_MTE3, EVENT_ID0);
    wait_flag(PIPE_MTE2, PIPE_MTE3, EVENT_ID0);
    TSTORE_IMPL<TileData, Global, AtomicType::AtomicNone>(dstG, tile);
    set_flag(PIPE_MTE3, PIPE_MTE2, EVENT_ID0);
    wait_flag(PIPE_MTE3, PIPE_MTE2, EVENT_ID0);
}
```

### Method selection

| Method | Advantages | Disadvantages | Applicability |
|------|------|------|------|
| TPUT\<AtomicAdd\> | Simple code, automatic pipeline synchronization | Low flexibility | Standard RS/AG scenario |
| TLOAD/TSTORE_IMPL | Custom logic can be inserted | Manual set_flag/wait_flag is required | Scenarios that require fine control |

---

## Mode 4: Computational fusion (computing + communication overlap)

The computing kernel and communication kernel are deployed on different AICore Blocks respectively, and overlap is achieved through Stream parallelism and queue synchronization.

```
computeStream: [GEMM Block 0] [GEMM Block 1] ... [GEMM Block N]
                     │              │                    │
                  Enqueue        Enqueue             Enqueue
                     │              │                    │
                     ▼              ▼                    ▼
commStream:    [RS: poll queues, TPUT<AtomicAdd>] → [Barrier] → [AG: TPUT<AtomicNone>]
```

### Key Design Elements

1. **Dual Stream**: Computational stream (Cube kernel) and communication stream (Vec kernel) are executed in parallel
2. **Ready Queue**: After the calculation is completed, the tile index is queued, and the communication kernel polls it out of the queue.
3. **Signal Matrix**: Cross-rank synchronization, ensuring that the RS phase is completed before starting AG
4. **Phase Barrier**: Inter-rank synchronization of multi-stage execution

### Ready queue design (SPSC lock-free queue)

```cpp
// Producer side (compute kernel):
PerBlockQueueEnqueueFast(cached_queue, tile_idx, local_slot);

// Consumer side (communication kernel): use TTEST hardware instruction polling
comm::Signal sig(const_cast<__gm__ int32_t *>(&queue->count));
if (!comm::TTEST(sig, local_head + 1, comm::WaitCmp::GE)) {
    return -1; // No new data
}
```
