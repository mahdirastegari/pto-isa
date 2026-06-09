# Host side and build system

## Standard initialization process

```cpp
int main(int argc, char **argv) {
    // 1. MPI initialization
    MPI_Init(&argc, &argv);
    int rank, nranks;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nranks);

    // 2. ACL initialization
    aclInit(nullptr);
    aclrtSetDevice(rank % device_count);
    aclrtStream computeStream, commStream;
    aclrtCreateStream(&computeStream);
    aclrtCreateStream(&commStream);

    // 3. HCCL communication domain creation
    HcclRootInfo rootInfo;
    if (rank == 0) HcclGetRootInfo(&rootInfo);
    MPI_Bcast(&rootInfo, sizeof(rootInfo), MPI_BYTE, 0, MPI_COMM_WORLD);
    HcclComm hcclComm;
    HcclCommInitRootInfo(nranks, &rootInfo, rank, &hcclComm);

    // 4. Get the communication context (remote address)

    // 5. Memory allocation
    uint8_t *buffer;
    aclrtMalloc((void**)&buffer, size, ACL_MEM_MALLOC_HUGE_FIRST);

    // 6. Signal matrix initialization (cleared)
    aclrtMemset(signal_matrix, 0, signal_size);

    // 7. Start kernel
    launchCommKernel(buffer, ..., commStream);
    aclrtSynchronizeStream(commStream);

    // 8. Verification results

    // 9. Cleanup
    HcclCommDestroy(hcclComm);
    aclrtDestroyStream(computeStream);
    aclrtDestroyStream(commStream);
    aclrtResetDevice(rank % device_count);
    aclFinalize();
    MPI_Finalize();
}
```

---

## Clear signal matrix

**Key**: The signal matrix must be cleared before each kernel execution, otherwise the last residual value will cause synchronization errors.

```cpp
aclrtMemset(signal_matrix, signal_size, 0, signal_size);
aclrtSynchronizeStream(stream);
```

---

## Kernel starts function mode

```cpp
// kernel_launchers.h declaration
void launchCommKernel(uint8_t *data, uint8_t *signal, uint8_t *ctx,
                      int rank, int nranks, void *stream);

// comm_kernel.cpp implementation
void launchCommKernel(uint8_t *data, uint8_t *signal, uint8_t *ctx,
                      int rank, int nranks, void *stream)
{
    CommKernelEntry<<<COMM_BLOCK_NUM, nullptr, stream>>>(
        data, signal, ctx, rank, nranks, COMM_BLOCK_NUM);
}
```

---

## CMakeLists.txt template

```cmake
cmake_minimum_required(VERSION 3.16)
project(my_comm_operator)

set(CMAKE_CXX_COMPILER bisheng)
set(CMAKE_CXX_STANDARD 17)

# PTO header file path (preferably use the version in the warehouse)
set(PTO_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../include")
include_directories(BEFORE ${PTO_INCLUDE_DIR})

# CANN environment
if(DEFINED ENV{ASCEND_HOME_PATH})
    set(ASCEND_HOME $ENV{ASCEND_HOME_PATH})
else()
    set(ASCEND_HOME "/usr/local/Ascend/ascend-toolkit/latest")
endif()
include_directories(${ASCEND_HOME}/include)
link_directories(${ASCEND_HOME}/lib64)

# Communication Kernel (Vec architecture)
add_library(comm_kernel SHARED comm_kernel.cpp)
target_compile_options(comm_kernel PRIVATE
    --cce-aicore-arch=dav-c220-vec
    -DMEMORY_BASE
    -D_GLIBCXX_USE_CXX11_ABI=0)
target_link_options(comm_kernel PRIVATE --cce-fatobj-link)
target_link_libraries(comm_kernel runtime)

# Computing Kernel (Cube architecture, if general computing integration is required)
add_library(compute_kernel SHARED compute_kernel.cpp)
target_compile_options(compute_kernel PRIVATE
    --cce-aicore-arch=dav-c220-cube
    -DMEMORY_BASE
    -D_GLIBCXX_USE_CXX11_ABI=0)
target_link_options(compute_kernel PRIVATE --cce-fatobj-link)
target_link_libraries(compute_kernel runtime)

# Host executable file
add_executable(my_operator main.cpp)
target_link_libraries(my_operator
    comm_kernel compute_kernel
    ascendcl hccl tiling_api platform)
```

### Key configuration items

| Configuration | Description |
|------|------|
| `--cce-aicore-arch=dav-c220-vec` | Communication kernel uses Vec architecture |
| `--cce-aicore-arch=dav-c220-cube` | Calculate kernel using Cube architecture |
| `-DMEMORY_BASE` | Enable remote address calculation macro |
| `--cce-fatobj-link` | Enable fat object linking |

---

## MPI run

```bash
# Single machine with multiple cards
mpirun -np 8 ./my_operator

# Multiple machines
mpirun -np 16 -H host1:8,host2:8 ./my_operator
```
