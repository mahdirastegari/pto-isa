# Synchronization and algorithm optimization

## Synchronization overhead optimization

### Barrier merge

Combine multiple phase barriers into one:

```
Before optimization: [RS] → [Barrier] → [local reduce] → [Barrier] → [AG]
After optimization: [RS with AtomicAdd] → [Barrier] → [AG]
         ^^^^^^^^^^^^^^^^^^^^^
         RS and Reduce are merged into TPUT<AtomicAdd>
```

By directly accumulating in the RS stage using `AtomicAdd`, a separate Reduce stage and its barrier are eliminated.

### Signal compression

Reduce the number of cross-rank notifications:

```
Before optimization: Notify the remote end of each tile completion → N_tiles × nranks times TNOTIFY
After optimization: Notify once when all tiles are completed → nranks times TNOTIFY
```

### Block role optimization

Only let block 0 execute cross-rank signals, and other blocks wait for local broadcast flags:

```
Block 0: TNOTIFY(remote) × (nranks-1) → TWAIT(local) × (nranks-1) → Set local flag
Block 1~N: TWAIT(local flag) ← TWAIT once instead of nranks times
```

### TTEST vs TWAIT Choice

| Scenario | Recommendation | Reason |
|------|------|------|
| Determined to wait (barrier) | TWAIT | Hardware spin, more energy-saving |
| Poll + do other work | TTEST | Interleaved execution |
| Ready queue consumption | TTEST | Check first and then process |

### Reduce dcci calls

`dcci` Refreshing cache lines is a scalar operation, and frequent calls affect performance:

```cpp
// Before optimization: dcci is used every time the queue data is read
for (int i = 0; i < count; i++) {
    dcci(&queue->data[i], SINGLE_CACHE_LINE);
    process(queue->data[i]);
}

// After optimization: use TTEST hardware instruction instead of dcci + software comparison
comm::Signal sig(&queue->count);
if (comm::TTEST(sig, expected, comm::WaitCmp::GE)) {
    dcci(&queue->data[head], SINGLE_CACHE_LINE);
    process(queue->data[head]);
}
```

---

## Algorithm selection

### AllReduce decomposition strategy

| Strategy | Traffic volume | Delay | Applicable scenarios |
|------|--------|------|---------|
| ReduceScatter + AllGather | 2(N-1)/N × S | 2(N-1) steps | Medium to large data volume |
| Ring AllReduce | 2(N-1)/N × S | 2(N-1) steps | Large data volume, limited bandwidth |
| Built-in TREDUCE + TBROADCAST | N × S | 2 steps | Small data volume, sufficient root bandwidth |
| TPUT\<AtomicAdd\> RS + TPUT AG | 2(N-1)/N × S | Overlapping possible | Computational fusion scenario |

Where S = total size of data, N = number of ranks.

### RS implementation: AtomicAdd vs standalone Reduce

**AtomicAdd method** (recommended for fusion):
- The RS phase uses `TPUT<AtomicAdd>` to directly accumulate to owner
- No need for independent Reduce stage and extra barrier
- There is a cumulative accuracy loss under FP16

**Independent Reduce method**:
- RS only does scatter (no reduction)
- owner executes TLOAD + TADD + TSTORE reduction locally
- Better accuracy, but requires extra stages and barriers

### AG implementation

- **TPUT direct write**: owner rank actively writes to all remote ends (recommended)
- **TGET pull**: Each rank is pulled from owner
- **TBROADCAST**: owner uses built-in collective communication broadcast

Usually choose **TPUT direct write** because the owner knows when the data is ready without additional notification.
