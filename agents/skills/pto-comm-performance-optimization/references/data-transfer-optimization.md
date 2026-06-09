# Data transfer optimization

## Ping Pong double buffering

### Principle

Use two UB Tiles working alternately, overlapping TLOAD (MTE2) and TSTORE (MTE3):

```
time →
MTE2:  [TLOAD ping] [TLOAD pong] [TLOAD ping] ...
MTE3:            [TSTORE ping] [TSTORE pong] ...
       ↑ No overlap ↑───── Overlapping area ──────↑
```

### Implementation pattern

```cpp
TileData pingTile(ROWS, COLS);
TileData pongTile(ROWS, COLS);
TASSIGN(pingTile, 0x0);
TASSIGN(pongTile, TILE_UB_BYTES);

// Method 1: Use the built-in ping-pong (recommended)
comm::TPUT(dstG, srcG, pingTile, pongTile);
comm::TGET(dstG, srcG, pingTile, pongTile);

// Method 2: manual ping-pong (more flexible)
for (int i = 0; i < num_chunks; i++) {
    bool use_ping = (i % 2 == 0);
    TileData &curTile = use_ping ? pingTile : pongTile;
    event_t curEv = use_ping ? EVENT_ID0 : EVENT_ID1;

    if (i > 0) {
        TileData &prevTile = use_ping ? pongTile : pingTile;
        event_t prevEv = use_ping ? EVENT_ID1 : EVENT_ID0;
        wait_flag(PIPE_MTE2, PIPE_MTE3, prevEv);
        TSTORE_IMPL<...>(prevDst, prevTile);
        set_flag(PIPE_MTE3, PIPE_MTE2, prevEv);
        wait_flag(PIPE_MTE3, PIPE_MTE2, prevEv);
    }

    TLOAD(curTile, srcG_i);
    set_flag(PIPE_MTE2, PIPE_MTE3, curEv);
}
// Flush the last tile
```

### When to use ping pong

| Scenario | Suggestions |
|------|------|
| Large number of small block transfers (multiple TLOAD/TSTORE) | Highly recommended |
| Single large block transfer | Not required (built-in instructions are automatically chunked) |
| UB space is tight | Use single buffering |
| Transfer volume > 2 x tile size | Recommended |

### Built-in vs manual ping-pong

- **Built-in** (ping-pong overload of TPUT/TGET): simple scenario, automatically handles pipeline synchronization
- **Manual**: Need to insert custom logic between TLOAD/TSTORE (such as AtomicAdd selection)

---

## Tile size selection

| Considerations | Impact |
|---------|------|
| UB capacity | Tile cannot exceed UB size (typical ~192KB) |
| Transmission efficiency | Large Tile: fewer transmissions, higher efficiency |
| Overlap granularity | Small tile: start communication earlier |
| Alignment | 32B alignment (row direction) |
| Ping-pong | Requires 2x tile space |

**Recommended Baseline** (half type):

```
UB about 192KB
Ping Pong mode requires 2 × Tile
Single Tile ≤ 96KB

128 × 256 × 2B = 64KB → safe, 128KB after ping pong
64 × 512 × 2B = 64KB → safe
256 × 256 × 2B = 128KB → Single buffer available, ping-pong dangerous
```

---

## Data alignment

```cpp
// Tile column number needs to be 32B aligned
constexpr int alignedCols = ((cols * sizeof(T) + 31) / 32) * (32 / sizeof(T));

// Align the interval between Tiles upward to 1024B
constexpr size_t TILE_UB_BYTES = ((M * N * sizeof(T) + 1023) / 1024) * 1024;
```

---

## GM data layout

The layout of communication data on GM affects transmission efficiency:

- **Continuous layout**: Best, TPUT/TGET is transferred in one time
- **Layout with step size**: automatically divided into blocks and transmitted by row, with additional overhead
- **Asynchronous transmission**: must be one-dimensionally continuous (constraints of TPUT_ASYNC/TGET_ASYNC)
