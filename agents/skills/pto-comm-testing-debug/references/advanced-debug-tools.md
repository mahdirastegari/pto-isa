# Advanced debugging tools

## mssanitizer memory detection

`mssanitizer` is the memory security detection tool of the Ascend platform, which can detect memory out-of-bounds, unaligned access and other issues in communication operators.

### Compile integration

Add sanitizer compilation option to CMakeLists.txt:

```cmake
option(ENABLE_SANITIZER "Enable mssanitizer for memory checking" OFF)

if(ENABLE_SANITIZER)
    target_compile_options(comm_kernel PRIVATE -fsanitize=memory)
    target_link_options(comm_kernel PRIVATE -fsanitize=memory)
    target_compile_options(compute_kernel PRIVATE -fsanitize=memory)
    target_link_options(compute_kernel PRIVATE -fsanitize=memory)
endif()
```

### How to use

```bash
# Compile the version with sanitizer
cmake .. -DENABLE_SANITIZER=ON
make -j

# Run (mssanitizer automatically detects)
mssanitizer --tool=memcheck mpirun -np 8 ./my_operator
```

### Detectable issues

| Problem type | Description | Typical scenarios in communication operators |
|---------|------|---------------------|
| GM out-of-bounds read | Reading a GM address beyond the allocated range | Boundary calculation error when Tile is divided |
| GM out-of-bounds write | Writing a GM address beyond the allocated range | Remote address offset calculation overflow |
| UB out of bounds | Access exceeds UB capacity | Tile size set too large |
| Unaligned access | Alignment requirements not met | Signal address not 4B aligned |

### Output interpretation

```
[mssanitizer] ERROR: out-of-bounds access at GM address 0x12345678
  in kernel CommKernelEntry at comm_kernel.cpp:142
  allocated at main.cpp:89 with size 65536
  accessed offset: 65540 (4 bytes beyond allocation)
```

Focus on:
- `out-of-bounds`: Check Tile boundaries and remote address calculation
- `use-after-free`: Check buffer life cycle
- `uninitialized`: Check whether the signal matrix is cleared

---

## Environment variable debugging

```bash
# HCCL Debugging
export HCCL_LOG_LEVEL=DEBUG # HCCL log level
export HCCL_BUFFSIZE=1024 # Communication buffer size (MB)

# ACL error code check
export ACL_ERROR_ABORT=1 # Abort immediately when encountering ACL errors
```

---

## Reduce the size of the problem

```cpp
#define DEBUG_MODE
#ifdef DEBUG_MODE
static constexpr uint32_t G_ORIG_M = 128;
static constexpr uint32_t G_ORIG_N = 256;
static constexpr int COMPUTE_BLOCK_NUM = 2;
static constexpr int COMM_BLOCK_NUM = 2;
#endif
```

---

## Host side performance timing

```cpp
aclrtEvent startEvent, endEvent;
aclrtCreateEvent(&startEvent);
aclrtCreateEvent(&endEvent);

aclrtRecordEvent(startEvent, stream);
launchKernel(..., stream);
aclrtRecordEvent(endEvent, stream);
aclrtSynchronizeStream(stream);

float elapsed_ms;
aclrtEventElapsedTime(&elapsed_ms, startEvent, endEvent);
printf("Kernel time: %.3f ms\n", elapsed_ms);
```

---

## Warmup + multiple measurements

```cpp
// Warmup (excluding first overhead)
for (int i = 0; i < WARMUP_ITERS; i++) {
    ClearSignals();
    LaunchKernel(...);
    aclrtSynchronizeStream(stream);
}

// formal measurement
float total_ms = 0;
for (int i = 0; i < MEASURE_ITERS; i++) {
    ClearSignals();
    aclrtRecordEvent(start, stream);
    LaunchKernel(...);
    aclrtRecordEvent(end, stream);
    aclrtSynchronizeStream(stream);
    float ms;
    aclrtEventElapsedTime(&ms, start, end);
    total_ms += ms;
}
printf("Average: %.3f ms\n", total_ms / MEASURE_ITERS);
```

---

## msprof Hardware Profiling

For Device-side pipeline-level analysis:

```bash
# Collect kernel execution timeline
msprof --output=./prof_data --application="mpirun -np 8 ./my_operator"

# Export analysis results
msprof --export=timeline --output=./prof_data
```

Can display MTE2/MTE3/Cube/Vec pipeline occupancy rate and locate communication/computing overlap holes.
