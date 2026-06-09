# Multi-block scheduling and address management

## Obtain remote address

The communication operator needs to know the GM address of the remote NPU. Commonly used methods:

### Method 1: Via HCCL communication window

```cpp
// Device side: Calculate the remote address
inline __gm__ half *GetRemotePtr(__gm__ DeviceContext *ctx, __gm__ half *local_ptr, int remote_rank)
{
    ptrdiff_t offset = reinterpret_cast<__gm__ uint8_t *>(local_ptr) -
                       reinterpret_cast<__gm__ uint8_t *>(ctx->windowsIn[ctx->myRank]);
    return reinterpret_cast<__gm__ half *>(
        reinterpret_cast<__gm__ uint8_t *>(ctx->windowsIn[remote_rank]) + offset);
}
```

### Method 2: Through ParallelGroup (collection communication)

```cpp
GlobalData tensors[NRANKS];
for (int r = 0; r < nranks; ++r) {
    tensors[r] = GlobalData(remote_addrs[r]);
}
comm::ParallelGroup<GlobalData> group(tensors, nranks, my_rank);
```

### Address alignment requirements

- All GM addresses must meet 32-byte alignment
- Signal address must be 4-byte aligned
- The workspace of TPUT_ASYNC/TGET_ASYNC is managed by a dedicated Manager and does not require additional alignment

---

## Block allocation strategy

```cpp
int block_idx = get_block_idx();
CommKernel<<<COMM_BLOCK_NUM, nullptr, stream>>>(..., COMM_BLOCK_NUM);
```

### Row-level equal distribution (recommended)

Eliminate ±1 imbalance:

```cpp
int total_rows = tile_count * ROWS_PER_TILE * (nranks - 1);
int rows_per_block = (total_rows + num_comm_blocks - 1) / num_comm_blocks;
int row_start = block_idx * rows_per_block;
int row_end = min((block_idx + 1) * rows_per_block, total_rows);

while (cur_row < row_end) {
    //Restore from flat row index (tile, rank, row_in_tile)
}
```

### Tile-level equal distribution

```cpp
int tiles_per_block = (total_tiles + num_blocks - 1) / num_blocks;
int my_start = block_idx * tiles_per_block;
int my_end = min(my_start + tiles_per_block, total_tiles);
```

### Block role differentiation

In scenarios such as barrier, block 0 plays a special role:

```cpp
if (block_idx == 0) {
    // block 0: perform cross-rank signal notification/waiting, and set the local broadcast flag after completion
} else {
    // Other blocks: wait for local broadcast flag
}
```

---

## Tiling strategy

### UB Tile size calculation

```cpp
static constexpr size_t TILE_UB_BYTES = ((BASE_M * BASE_N * sizeof(half) + 1023) / 1024) * 1024;
```

### Dimension alignment

```cpp
static constexpr uint32_t CeilDiv(uint32_t a, uint32_t b) { return (a + b - 1) / b; }
static constexpr uint32_t AlignUp(uint32_t a, uint32_t b) { return CeilDiv(a, b) * b; }

static constexpr uint32_t G_M = AlignUp(ORIG_M, BASE_M);
static constexpr uint32_t G_N = AlignUp(ORIG_N, BASE_N);
static constexpr uint32_t NUM_TILES = (G_M / BASE_M) * (G_N / BASE_N);
```

### UB Buffer Planning

```
UB layout (ping pong mode):
┌──────────────┬──────────────┐
│  pingTile    │  pongTile    │
│  0x0         │  TILE_UB     │
│  BASE_M ×    │  BASE_M ×    │
│  BASE_N ×    │  BASE_N ×    │
│  sizeof(T)   │  sizeof(T)   │
└──────────────┴──────────────┘
```

Alignment requirements:
- Tile rows are aligned to 32 bytes (for RowMajor, cols × sizeof(T) requires 32B alignment)
- Separate tiles by at least TILE_UB_BYTES (to avoid overlap)
