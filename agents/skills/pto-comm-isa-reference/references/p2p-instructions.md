# Detailed explanation of P2P instructions (TPUT/TGET)

## TPUT — remote write

**Data flow**: `srcGlobalData(local GM)` → `stagingTileData(UB)` → `dstGlobalData(remote GM)`

When GlobalTensor exceeds the UB Tile capacity, two-dimensional sliding tiling is automatically performed.

### Interface signature

```cpp
// Single Tile (automatic chunking) - compile-time atomic type
template <AtomicType atomicType = AtomicType::AtomicNone,
          typename GlobalDstData, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TPUT(GlobalDstData &dst, GlobalSrcData &src, TileData &stagingTile, WaitEvents&... events);

// Single Tile — Runtime atomic type
template <typename GlobalDstData, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TPUT(GlobalDstData &dst, GlobalSrcData &src, TileData &stagingTile,
                 AtomicType atomicType, WaitEvents&... events);

// Ping Pong double buffering
template <AtomicType atomicType = AtomicType::AtomicNone,
          typename GlobalDstData, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TPUT(GlobalDstData &dst, GlobalSrcData &src,
                 TileData &pingTile, TileData &pongTile, WaitEvents&... events);
```

### Constraints

- `GlobalSrcData::RawDType == GlobalDstData::RawDType`
- `TileData::DType == GlobalSrcData::RawDType`
- `GlobalSrcData::layout == GlobalDstData::layout`
- `dstGlobalData` must point to the remote address
- `srcGlobalData` must point to a local address
- `stagingTileData` must be allocated in UB beforehand
- Ping-Pong mode: `pingTile` and `pongTile` must be of the same type and dimension, with non-overlapping UB offsets
- `atomicType` supports `AtomicNone` and `AtomicAdd`

### Example

```cpp
//Basic remote writing
comm::TPUT(dstG, srcG, stagingTile);

// Remote write with atomic addition
comm::TPUT<AtomicType::AtomicAdd>(dstG, srcG, stagingTile);

// Ping-pong double buffering (automatic chunking)
constexpr size_t tileUBBytes = ((64 * 64 * sizeof(float) + 1023) / 1024) * 1024;
TileT pingTile(64, 64);
TileT pongTile(64, 64);
TASSIGN(pingTile, 0);
TASSIGN(pongTile, tileUBBytes);
comm::TPUT(dstG, srcG, pingTile, pongTile);

//Select the atom type at runtime
comm::TPUT(dstG, srcG, stagingTile, AtomicType::AtomicAdd);
```

---

## TGET — remote read

**Data flow**: `srcGlobalData(remote GM)` → `stagingTileData(UB)` → `dstGlobalData(local GM)`

### Interface signature

```cpp
//Single Tile
template <typename GlobalDstData, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TGET(GlobalDstData &dst, GlobalSrcData &src, TileData &stagingTile, WaitEvents&... events);

// Ping Pong double buffering
template <typename GlobalDstData, typename GlobalSrcData, typename TileData, typename... WaitEvents>
RecordEvent TGET(GlobalDstData &dst, GlobalSrcData &src,
                 TileData &pingTile, TileData &pongTile, WaitEvents&... events);
```

### Constraints

- Similar to TPUT, but in the opposite direction
- `srcGlobalData` points to the remote end, `dstGlobalData` points to the local one
- TGET does not support atomic operations

### Example

```cpp
//Basic remote reading
comm::TGET(dstG, srcG, stagingTile);

//Ping Pong double buffered remote read
comm::TGET(dstG, srcG, pingTile, pongTile);
```
