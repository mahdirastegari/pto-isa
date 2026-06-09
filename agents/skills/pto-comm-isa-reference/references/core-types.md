# Detailed explanation of core types

## Signal — scalar signal

Used for single flag synchronization, encapsulating the GM address of type `int32_t`:

```cpp
using Signal = GlobalTensor<int32_t, Shape<1,1,1,1,1>, Stride<1,1,1,1,1>, Layout::ND>;

comm::Signal sig(ptr);  // ptr: __gm__ int32_t*
```

## Signal2D — two-dimensional signal matrix

Compile-time shaped 2D signal grid, supporting dense layout and sub-region views:

```cpp
//Dense 4×8 grid (step size automatically derived to 8)
comm::Signal2D<4, 8> grid(ptr);

// From subregions in a large 128-column grid (step = 128)
comm::Signal2D<4, 8> sub(ptr + offset, 128);
```

## ParallelGroup — Collection communication group

A lightweight view that encapsulates a multi-rank `GlobalTensor` object array:

```cpp
template <typename GlobalData>
struct ParallelGroup {
    GlobalData *tensors; // GlobalTensor array for each rank
    int nranks; //Total number of ranks
    int rootIdx; //rank index of root NPU

    static ParallelGroup Create(GlobalData *tensorArray, int size, int rootIdx);
};
```

**Key Constraints**:
- `tensors` points to an external array (no dynamic memory allocation)
- `rootIdx` is the index of root rank in the group, all ranks must pass in the same `rootIdx`
- Access by team rank index via `operator[]`

## NotifyOp — notification operation type

| value | description |
|----|------|
| `NotifyOp::AtomicAdd` | Atomic addition (`signal += value`) |
| `NotifyOp::Set` | Direct assignment (`signal = value`) |

## WaitCmp — comparison operator

| value | description |
|----|------|
| `WaitCmp::EQ` | Equals (`==`) |
| `WaitCmp::NE` | Not equal to (`!=`) |
| `WaitCmp::GT` | Greater than (`>`) |
| `WaitCmp::GE` | Greater than or equal to (`>=`) |
| `WaitCmp::LT` | Less than (`<`) |
| `WaitCmp::LE` | Less than or equal to (`<=`) |

## ReduceOp — reduction operator

| value | description |
|----|------|
| `ReduceOp::Sum` | Element-wise summation |
| `ReduceOp::Max` | Get the maximum value element by element |
| `ReduceOp::Min` | Get the minimum value element by element |

## AtomicType — Atomic operation type

Defined in `include/pto/common/constants.hpp`:

| value | description |
|----|------|
| `AtomicType::AtomicNone` | No atomic operations (default) |
| `AtomicType::AtomicAdd` | Atomic addition operation |

## DmaEngine — DMA engine selection

| value | description |
|----|------|
| `DmaEngine::SDMA` | SDMA engine, supports two-dimensional transmission |
| `DmaEngine::URMA` | URMA engine, supports one-dimensional transmission (Ascend950 / NPU_ARCH 3510 only) |

## AsyncEvent — Asynchronous event handler

```cpp
struct AsyncEvent {
    uint64_t handle;
    DmaEngine engine;

    bool valid() const; // return true when handle != 0
    bool Wait(const AsyncSession &session) const; // Block until transfer is completed
    bool Test(const AsyncSession &session) const; // Non-blocking completion detection
};
```

## AsyncSession — Asynchronous session

Engine-independent session object, built through `BuildAsyncSession<engine>()`:

```cpp
struct AsyncSession {
    DmaEngine engine;
    sdma::SdmaSession sdmaSession;
    urma::UrmaSession urmaSession;
    bool valid;
};
```
