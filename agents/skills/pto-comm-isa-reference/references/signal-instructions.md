# Detailed explanation of signal synchronization instructions (TNOTIFY / TWAIT / TTEST)

## TNOTIFY — Send signal notification

Send flag notifications to the remote NPU for lightweight synchronization.

```cpp
template <typename GlobalSignalData, typename... WaitEvents>
void TNOTIFY(GlobalSignalData &dstSignalData, int32_t value, NotifyOp op, WaitEvents&... events);
```

### Constraints

- `GlobalSignalData::DType` must be `int32_t`
- `dstSignalData` must point to the remote address (target NPU)
- `dstSignalData` should be 4-byte aligned
- `NotifyOp::Set` performs direct storage
- `NotifyOp::AtomicAdd` uses hardware atomic add instructions

### Example

```cpp
// Direct assignment notification
comm::Signal sig(remote_signal);
comm::TNOTIFY(sig, 1, comm::NotifyOp::Set);

// Atomic counter increments
comm::Signal counter(remote_counter);
comm::TNOTIFY(counter, 1, comm::NotifyOp::AtomicAdd);
```

**IMPORTANT**: TNOTIFY is sent to the **remote** address, TWAIT/TTEST detects the **local** address. Pay attention to the address direction when using in pairs.

---

## TWAIT — Block waiting for a signal

Blocks and waits until the signal meets the comparison condition.

```cpp
template <typename GlobalSignalData, typename... WaitEvents>
void TWAIT(GlobalSignalData &signalData, int32_t cmpValue, WaitCmp cmp, WaitEvents&... events);
```

### Constraints

- `GlobalSignalData::DType` must be `int32_t`
- `signalData` must point to the **local** address (current NPU)
- Supports single signal and multi-dimensional signal tensor (up to 5 dimensions)
- For tensor, **all** signals must meet the conditions before they are returned

### Example

```cpp
// Wait for a single signal
comm::Signal sig(local_signal);
comm::TWAIT(sig, 1, comm::WaitCmp::EQ);

// Waiting signal matrix (all elements of 4×8 grid >= 1)
comm::Signal2D<4, 8> grid(signal_matrix);
comm::TWAIT(grid, 1, comm::WaitCmp::GE);

// Wait for the counter to reach the threshold
comm::TWAIT(counter, expected_count, comm::WaitCmp::GE);
```

---

## TTEST — Non-blocking signal detection

Non-blocking heartbeat condition, returns `bool`.

```cpp
template <typename GlobalSignalData, typename... WaitEvents>
bool TTEST(GlobalSignalData &signalData, int32_t cmpValue, WaitCmp cmp, WaitEvents&... events);
```

### Constraints

Same as TWAIT, but does not block.

### Example

```cpp
// Non-blocking detection
bool ready = comm::TTEST(sig, 1, comm::WaitCmp::EQ);

//Polling with timeout
for (int i = 0; i < max_iters; ++i) {
    if (comm::TTEST(sig, 1, comm::WaitCmp::EQ)) {
        break;
    }
}
```

---

## TWAIT vs TTEST Selection Guide

| Scenario | Recommendation | Reason |
|------|------|------|
| Determined to wait (barrier) | TWAIT | Hardware spin, more energy-saving |
| Other work needs to be performed during the waiting period | TTEST | Interleaved execution possible |
| Timeout control is required | TTEST | Loop upper limit can be set |
| Ready queue consumption | TTEST | Check first and then process |
