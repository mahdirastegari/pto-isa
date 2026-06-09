# Detailed explanation of asynchronous communication instructions (TPUT_ASYNC / TGET_ASYNC / BuildAsyncSession)

## TPUT_ASYNC — Asynchronous remote writing

Start GM→GM DMA transfer and return `AsyncEvent` immediately.

```cpp
template <DmaEngine engine = DmaEngine::SDMA,
          typename GlobalDstData, typename GlobalSrcData, typename... WaitEvents>
AsyncEvent TPUT_ASYNC(GlobalDstData &dst, GlobalSrcData &src,
                      const AsyncSession &session, WaitEvents&... events);
```

## TGET_ASYNC — Asynchronous remote read

Start remote GM→local GM DMA transfer.

```cpp
template <DmaEngine engine = DmaEngine::SDMA,
          typename GlobalDstData, typename GlobalSrcData, typename... WaitEvents>
AsyncEvent TGET_ASYNC(GlobalDstData &dst, GlobalSrcData &src,
                      const AsyncSession &session, WaitEvents&... events);
```

---

## BuildAsyncSession — Build an asynchronous session

### SDMA build (default)

```cpp
template <DmaEngine engine = DmaEngine::SDMA, typename ScratchTile>
bool BuildAsyncSession(ScratchTile &scratchTile, __gm__ uint8_t *workspace,
                       AsyncSession &session,
                       uint32_t syncId = 0,
                       const sdma::SdmaBaseConfig &baseConfig = {sdma::kDefaultSdmaBlockBytes, 0, 1},
                       uint32_t channelGroupIdx = sdma::kAutoChannelGroupIdx);
```

| Parameters | Description |
|------|------|
| `scratchTile` | UB scratch tile for SDMA control metadata (non-data payload), recommended `Tile<TileType::Vec, uint8_t, 1, comm::sdma::UB_ALIGN_SIZE>` (256B) |
| `workspace` | GM pointer allocated by Host side `SdmaWorkspaceManager` |
| `syncId` | MTE3/MTE2 pipeline synchronization event ID (0-7) to avoid conflict with other pipeline barriers in the kernel |
| `baseConfig` | `{block_bytes, comm_block_offset, queue_num}`, applicable to single queue scenario by default |
| `channelGroupIdx` | SDMA channel group index, mapped using `get_block_idx()` by default |

### URMA build (Ascend950/NPU_ARCH 3510 only)

```cpp
bool BuildAsyncSession(__gm__ uint8_t *workspace, uint32_t destRankId, AsyncSession &session);
```

---

## Asynchronous constraints

- **Only supports flat continuous logical one-dimensional tensor** (non-one-dimensional returns invalid event)
- SDMA workspace must be allocated by the Host side `SdmaWorkspaceManager`
- URMA workspace must be allocated by the Host side `UrmaWorkspaceManager`
- URMA requires large page memory (`ACL_MEM_MALLOC_HUGE_ONLY`), small page allocation causes registration failure
- `scratchTile` is only used to control metadata, not the data temporary buffer

---

## Completion semantics (Quiet semantics)

- `event.Wait(session)` blocks until all asynchronous operations issued since the last Wait are completed
- After multiple asynchronous calls, only call `Wait` once for the last `AsyncEvent`
- shmem-like quiet semantics

---

## Complete example

```cpp
// Build session
using ScratchTile = Tile<TileType::Vec, uint8_t, 1, comm::sdma::UB_ALIGN_SIZE>;
ScratchTile scratchTile;
TASSIGN(scratchTile, 0x0);

comm::AsyncSession session;
if (!comm::BuildAsyncSession<comm::DmaEngine::SDMA>(scratchTile, sdmaWorkspace, session)) {
    return;
}

// Batch transfer + one Wait
comm::AsyncEvent lastEvent;
for (int rank = 0; rank < nranks; ++rank) {
    GT dstG(remoteDst + rank * size, shape, stride);
    lastEvent = comm::TPUT_ASYNC(dstG, srcG, session);
}
(void)lastEvent.Wait(session); // Wait for all pending operations to complete
```
