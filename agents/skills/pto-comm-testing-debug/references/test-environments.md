# Test environment and operation

## CPU simulation test

### Scope of application

CPU simulation supports functional verification of the following synchronous communication instructions:
- TPUT, TGET (P2P transmission)
- TNOTIFY, TWAIT, TTEST (signal synchronization)
- TGATHER, TSCATTER, TBROADCAST, TREDUCE (aggregate communication)

**Not supported**: Asynchronous instructions (TPUT_ASYNC/TGET_ASYNC) directly return empty events under CPU simulation.

### Operation mode

```bash
python3 tests/run_cpu.py --testcase <testcase_name> --gtest_filter '<filter>'

# Example
python3 tests/run_cpu.py --testcase tgather --gtest_filter 'TGatherTest.*'
```

### CPU emulation limitations

| Features | CPU Emulation | NPU Hardware |
|------|---------|---------|
| Functional correctness | Verify data calculation logic | Verify complete execution |
| Remote address | Simulated as local pointer | Real hardware remote DMA |
| Signal synchronization | Simulation AtomicAdd/Set | Hardware atomic operations |
| pipe_barrier | Ignore | Real pipeline synchronization |
| Multi-rank | Single-process simulation | MPI + multiple NPU |
| Asynchronous DMA | Returning invalid event | SDMA/URMA engine |

**Recommendation**: CPU emulation verifies data flow and logic correctness, but ultimately synchronization and performance must be verified on NPU hardware.

---

## NPU hardware test

### Single instruction ST test

```bash
python3 tests/script/run_st.py -r npu -v a3 -t tput -g TPutTest.*

# Run all communications ST
python3 tests/script/run_st.py -r npu -v a3 --comm
```

### Operator level test

```bash
cd kernels/manual/a2a3/my_operator
mkdir -p build && cd build
cmake .. -DSOC_VERSION=Ascend910C -DRUN_MODE=npu
make -j

# Run (8 ranks)
mpirun -np 8 ./my_operator
```

### Test Kernel structure

```cpp
template <typename T, int Rows, int Cols>
__global__ AICORE void TPutTestKernel(__gm__ T *local_data, __gm__ T *remote_addr)
{
    using ShapeDyn = Shape<DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC>;
    using StrideDyn = Stride<DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC, DYNAMIC>;
    using Global = GlobalTensor<T, ShapeDyn, StrideDyn, Layout::ND>;
    using TileT = Tile<TileType::Vec, T, Rows, Cols, BLayout::RowMajor, -1, -1>;

    ShapeDyn shape(1, 1, 1, Rows, Cols);
    StrideDyn stride(Rows * Cols, Rows * Cols, Rows * Cols, Cols, 1);

    Global srcG(local_data, shape, stride);
    Global dstG(remote_addr, shape, stride);

    TileT stagingTile(Rows, Cols);
    TASSIGN(stagingTile, 0x0);

    comm::TPUT(dstG, srcG, stagingTile);
}
```

---

## Multi-Rank testing framework

### MPI Wrapper

Use dynamic loading to avoid hard dependencies:

```cpp
class MpiWrapper {
    void *handle_;
    int (*MPI_Init_)(int*, char***);
    int (*MPI_Comm_rank_)(MPI_Comm, int*);
public:
    MpiWrapper() {
        handle_ = dlopen("libmpi.so", RTLD_LAZY);
        MPI_Init_ = (decltype(MPI_Init_))dlsym(handle_, "MPI_Init");
    }
};
```

### Test run script template

```bash
#!/bin/bash
set -e

source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh

mkdir -p build && cd build
cmake .. -DSOC_VERSION=${SOC_VERSION:-Ascend910C} -DRUN_MODE=npu
make -j$(nproc)
cd ..

NRANKS=${NRANKS:-8}
export HCCL_BUFFSIZE=1024

mpirun -np $NRANKS \
    --allow-run-as-root \
    -x LD_LIBRARY_PATH \
    -x ASCEND_HOME_PATH \
    ./build/my_operator "$@"
```

### Rank 0 Collect results

```cpp
if (rank == 0) {
    bool pass = VerifyResult(actual, golden, count);
    int result = pass ? 0 : 1;
    MPI_Bcast(&result, 1, MPI_INT, 0, MPI_COMM_WORLD);
    printf("Overall: %s\n", pass ? "PASS" : "FAIL");
} else {
    int result;
    MPI_Bcast(&result, 1, MPI_INT, 0, MPI_COMM_WORLD);
}
```
