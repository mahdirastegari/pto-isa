# Correctness verification method

## Golden data generation

### Python Golden generation script template

```python
#!/usr/bin/python3
import os
import numpy as np
np.random.seed(42)

def gen_reduce_scatter_golden(nranks, M, N, dtype=np.float16):
    """Generate golden data of ReduceScatter"""
    inputs = []
    for r in range(nranks):
        data = np.random.randn(M, N).astype(dtype)
        data.tofile(f"rank{r}_input.bin")
        inputs.append(data)

    summed = np.sum(inputs, axis=0)

    for r in range(nranks):
        golden = np.zeros_like(summed)
        # Fill in the results that rank r should hold according to the tiling strategy
        golden.tofile(f"rank{r}_golden.bin")

def gen_allgather_golden(nranks, M, N, dtype=np.float16):
    """Generate AllGather's golden data: each rank holds the complete summed result"""
    inputs = []
    for r in range(nranks):
        data = np.fromfile(f"rank{r}_input.bin", dtype=dtype).reshape(M, N)
        inputs.append(data)

    golden = np.sum(inputs, axis=0)
    for r in range(nranks):
        golden.tofile(f"rank{r}_allreduce_golden.bin")

if __name__ == "__main__":
    nranks = 8
    M, N = 5416, 1408
    gen_reduce_scatter_golden(nranks, M, N)
    gen_allgather_golden(nranks, M, N)
```

### Golden Data Organization

```
testdata/
├── rank0_input.bin
├── rank1_input.bin
├── ...
├── rank0_golden.bin
├── rank1_golden.bin
├── ...
└── config.json
```

### Data type mapping

| Python numpy | C++ types | ACL types |
|-------------|---------|----------|
| `np.float16` | `half` | `aclFloat16` |
| `np.float32` | `float` | `float` |
| `np.int32` | `int32_t` | `int32_t` |
| `np.int16` | `int16_t` | `int16_t` |

---

## Verification function template

```cpp
template <typename T>
bool VerifyResult(const T *actual, const T *expected, size_t count,
                  float atol = 1.0f, float rtol = 0.01f)
{
    int error_count = 0;
    int max_errors = 10;
    float max_diff = 0.0f;

    for (size_t i = 0; i < count; ++i) {
        float a = static_cast<float>(actual[i]);
        float e = static_cast<float>(expected[i]);
        float diff = std::abs(a - e);
        float threshold = atol + rtol * std::abs(e);

        if (diff > threshold) {
            if (error_count < max_errors) {
                printf("  Mismatch at [%zu]: actual=%f, expected=%f, diff=%f, threshold=%f\n",
                       i, a, e, diff, threshold);
            }
            error_count++;
            max_diff = std::max(max_diff, diff);
        }
    }

    if (error_count > 0) {
        printf("  Total errors: %d / %zu (max_diff=%f)\n", error_count, count, max_diff);
    }
    return error_count == 0;
}
```

---

## Accuracy standard

| Data type | Recommend atol | Recommend rtol | Description |
|---------|----------|----------|------|
| float (FP32) | 1e-5 | 1e-4 | High precision |
| half (FP16) | 1.0 | 0.01 | AtomicAdd has a large cumulative error |
| int32 / int16 | 0 | 0 | exact match |

**FP16 AtomicAdd precision note**:
- Multi-rank AtomicAdd accumulation will introduce floating point errors
- The greater the number of ranks, the greater the cumulative error
- It is recommended that FP16 use `atol=1.0, rtol=0.01` or looser thresholds

---

## Phased verification

For multi-stage operators (such as RS + Barrier + AG), it is recommended to verify in stages:

```cpp
// Phase 1 verification: after RS completes, check reduced_output
RunReduceScatterOnly(...);
aclrtSynchronizeStream(stream);
bool rs_pass = VerifyReduceScatter(reduced_output, rs_golden);

// Phase 2 Verification: After complete AllReduce, check the final result
RunFullAllReduce(...);
aclrtSynchronizeStream(stream);
bool ar_pass = VerifyAllReduce(reduced_output, ar_golden);
```

---

## main.cpp template (multi-rank test)

```cpp
#include "acl/acl.h"
#include "comm_mpi.h"
#include "hccl_context.h"
#include <cstdio>

extern void launchTPutTest(uint8_t *local, uint8_t *remote, void *stream);

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    int rank, nranks;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nranks);

    aclInit(nullptr);
    aclrtSetDevice(rank);
    aclrtStream stream;
    aclrtCreateStream(&stream);

    HcclRootInfo rootInfo;
    if (rank == 0) HcclGetRootInfo(&rootInfo);
    MPI_Bcast(&rootInfo, sizeof(rootInfo), MPI_BYTE, 0, MPI_COMM_WORLD);
    HcclComm comm;
    HcclCommInitRootInfo(nranks, &rootInfo, rank, &comm);

    size_t dataSize = ROWS * COLS * sizeof(half);
    uint8_t *localBuf, *remoteBuf;
    // ... get the communication window address ...

    std::vector<half> hostData(ROWS * COLS);
    for (int i = 0; i < ROWS * COLS; i++) hostData[i] = (half)(rank * 1000 + i);
    aclrtMemcpy(localBuf, dataSize, hostData.data(), dataSize, ACL_MEMCPY_HOST_TO_DEVICE);

    MPI_Barrier(MPI_COMM_WORLD);

    launchTPutTest(localBuf, remoteBuf, stream);
    aclrtSynchronizeStream(stream);

    MPI_Barrier(MPI_COMM_WORLD);

    std::vector<half> result(ROWS * COLS);
    aclrtMemcpy(result.data(), dataSize, localBuf, dataSize, ACL_MEMCPY_DEVICE_TO_HOST);

    bool pass = true;
    for (int i = 0; i < ROWS * COLS; i++) {
        half expected = /* calculated based on communication semantics */;
        if (abs((float)result[i] - (float)expected) > 1e-3) {
            printf("FAIL: rank %d, idx %d, got %f, expected %f\n",
                   rank, i, (float)result[i], (float)expected);
            pass = false;
            break;
        }
    }
    printf("Rank %d: %s\n", rank, pass ? "PASS" : "FAIL");

    HcclCommDestroy(comm);
    aclrtDestroyStream(stream);
    aclrtResetDevice(rank);
    aclFinalize();
    MPI_Finalize();
    return pass ? 0 : 1;
}
```
