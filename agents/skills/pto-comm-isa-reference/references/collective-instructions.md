# Detailed explanation of collective communication instructions (TGATHER / TSCATTER / TBROADCAST / TREDUCE)

All collective communication instructions share the following characteristics:
- Only **root** performs the call, non-root may not call (undefined behavior)
- Specify participants based on `ParallelGroup`
- Supports single buffering and ping-pong double buffering
- Automatic two-dimensional sliding tiles when data exceeds UB Tile

---

## TGATHER — Multi-rank collection

Root collects data from all ranks, spliced along DIM_3.

```cpp
// single buffer
template <typename ParallelGroupType, typename GlobalDstData, typename TileData, typename... WaitEvents>
RecordEvent TGATHER(ParallelGroupType &group, GlobalDstData &dst,
                    TileData &stagingTile, WaitEvents&... events);

// ping pong
template <typename ParallelGroupType, typename GlobalDstData, typename TileData, typename... WaitEvents>
RecordEvent TGATHER(ParallelGroupType &group, GlobalDstData &dst,
                    TileData &pingTile, TileData &pongTile, WaitEvents&... events);
```

### Constraints

- `dstGlobalData` points to local memory, `GetShape(DIM_3)` must be ≥ `N × H`
- `parallelGroup.tensors[r]` points to the remote source buffer of rank r
- All source tensors must have the same shape and stride
- Tile blocking constraints: static `ValidRow`/`ValidCol` must be divisible by the corresponding dimension

### Example

```cpp
GPerRank tensors[NRANKS];
for (int i = 0; i < NRANKS; ++i) tensors[i] = GPerRank(group_addrs[i]);

comm::ParallelGroup<GPerRank> group(tensors, NRANKS, my_rank);
GResult dstG(result);
TileT stagingTile(TILE_ROWS, TILE_COLS);
comm::TGATHER(group, dstG, stagingTile);
```

---

## TSCATTER — distributed from root

Root splits the data along DIM_3 and distributes it to each rank. The reverse operation of TGATHER.

```cpp
// single buffer
template <typename ParallelGroupType, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TSCATTER(ParallelGroupType &group, GlobalSrcData &src,
                     TileData &stagingTile, WaitEvents&... events);

// ping pong
template <typename ParallelGroupType, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TSCATTER(ParallelGroupType &group, GlobalSrcData &src,
                     TileData &pingTile, TileData &pongTile, WaitEvents&... events);
```

### Constraints

- `srcGlobalData` points to local memory, `GetShape(DIM_3)` must be ≥ `N × H`
- `parallelGroup.tensors[r]` points to the remote target buffer of rank r

---

## TBROADCAST — Broadcast

Root broadcasts local data to all ranks.

```cpp
// single buffer
template <typename ParallelGroupType, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TBROADCAST(ParallelGroupType &group, GlobalSrcData &src,
                       TileData &stagingTile, WaitEvents&... events);

// ping pong
template <typename ParallelGroupType, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TBROADCAST(ParallelGroupType &group, GlobalSrcData &src,
                       TileData &pingTile, TileData &pongTile, WaitEvents&... events);
```

### Constraints

- `srcGlobalData` points to local memory
- `parallelGroup.tensors[k]` points to the remote target buffer of rank k

---

## TREDUCE — multi-rank reduction

Root collects data from all ranks and performs element-wise reduction.

```cpp
// Basic reduce (accumulate Tile + receive Tile)
template <typename ParallelGroupType, typename GlobalDstData, typename TileData, typename... WaitEvents>
RecordEvent TREDUCE(ParallelGroupType &group, GlobalDstData &dst,
                    TileData &accTile, TileData &recvTile, ReduceOp op, WaitEvents&... events);

// ping pong reduce
template <typename ParallelGroupType, typename GlobalDstData, typename TileData, typename... WaitEvents>
RecordEvent TREDUCE(ParallelGroupType &group, GlobalDstData &dst,
                    TileData &accTile, TileData &pingTile, TileData &pongTile,
                    ReduceOp op, WaitEvents&... events);
```

### Constraints

- `dstGlobalData` points to local memory
- `accTileData`, `recvTileData` (or `accTile` + `pingTile` + `pongTile`) must be pre-allocated UB Tile
- `parallelGroup.tensors[r]` points to the remote source buffer of rank r
- Blocking constraints are the same as TGATHER

### Example

```cpp
comm::ParallelGroup<GTensor> group(tensors, NRANKS, my_rank);
GTensor dstG(result);
TileT accTile, recvTile;
comm::TREDUCE(group, dstG, accTile, recvTile, comm::ReduceOp::Sum);
```
