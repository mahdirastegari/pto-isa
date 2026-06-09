# Problem Diagnosis Manual

## 1. Deadlock (program hangs)

**Symptoms**: Program unresponsive, `mpirun` times out.

### Troubleshooting steps

| Check items | Methods | Typical causes |
|--------|------|---------|
| TWAIT does not match TNOTIFY | Check whether each TWAIT has a corresponding TNOTIFY to send | Missing notification or sending in the wrong direction |
| Barrier asymmetry | Confirm that all ranks execute barrier | Some ranks skip barrier paths |
| Signal address error | Print signal address to confirm that the remote/local address is correct | Remote address calculation error |
| Block number does not match | Confirm intra-rank counter expected value | `num_comm_blocks - 1` does not match actual value |

### Timeout protection mode

```cpp
int timeout = 1000000;
while (timeout-- > 0) {
    if (comm::TTEST(sig, expected, comm::WaitCmp::GE)) break;
}
if (timeout <= 0) {
    dcci((__gm__ void *)signal_ptr, SINGLE_CACHE_LINE);
    //Log exception
}
```

---

## 2. Data error

| Phenomenon | Possible causes | Solutions |
|------|---------|---------|
| All zeros | Transfer not executed/address error | Check remote address calculation and kernel startup |
| Random value | Read into uninitialized memory | Check whether signal synchronization is correct (write first, then read) |
| Partially correct | Tiling boundary issues | Check AlignUp and Tile boundary handling |
| NaN/Inf | FP16 overflow | Check AtomicAdd accumulation times and data range |
| Close but not exact | FP16 precision limits | Relax atol/rtol thresholds |

---

## 3. Signal residue

**Symptoms**: The first run is correct, the second run results are wrong or the barrier is passed early.

**Cause**: The signal matrix is not cleared before each run.

**Fix**:

```cpp
aclrtMemset(signal_matrix, signal_size, 0, signal_size);
aclrtSynchronizeStream(stream);
```

---

## 4. Compilation error

| Error message | Cause | Solution |
|---------|------|------|
| `MEMORY_BASE` undefined | Missing compile option `-DMEMORY_BASE` | CMakeLists added target_compile_definitions |
| `comm::` symbol not found | `pto_comm_inst.hpp` not included | Check include path |
| `__gm__` undefined | CPU compiled with NPU type | Check `#ifdef __CCE_AICORE__` conditional compilation |
| link error: runtime | Runtime library not linked | CMakeLists add `target_link_libraries(... runtime)` |

---

## 5. TPUT_ASYNC returns invalid event

**Symptoms**: `event.valid()` returns false (handle == 0).

**Reason**:
- The incoming tensor is not a flat continuous one-dimensional
- BuildAsyncSession failed (invalid workspace)
- A5 platform MTE fallback returns handle=0 when completed (normal behavior)

**Troubleshooting**:

```cpp
auto event = comm::TPUT_ASYNC(dstG, srcG, session);
if (!event.valid()) {
    // Check session.valid
    // Check whether the tensor is one-dimensionally continuous
    // MTE fallback under A5 platform has been completed, no need to wait
}
```

---

## 6. dcci cache consistency problem

**Symptoms**: Device reads stale data.

**Cause**: AICore read GM may hit the L1 cache and not see writes from other cores.

**Solution**:

```cpp
dcci((__gm__ void *)&shared_data, SINGLE_CACHE_LINE);
__asm__ __volatile__(""); // Compiler barrier
int32_t value = shared_data;
```
