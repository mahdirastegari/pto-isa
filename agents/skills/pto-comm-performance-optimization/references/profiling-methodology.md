# Performance analysis method

## Bandwidth estimation

```cpp
// RS stage data volume
size_t rs_bytes = (nranks - 1) * total_data_bytes / nranks;

//Amount of data in AG stage
size_t ag_bytes = (nranks - 1) * total_data_bytes / nranks;

//actual bandwidth
float rs_bw_gbps = rs_bytes / (rs_time_us * 1e-6) / 1e9;
float ag_bw_gbps = ag_bytes / (ag_time_us * 1e-6) / 1e9;

// Theoretical peak bandwidth (example: ~30GB/s within HCCS node)
float peak_bw_gbps = 30.0;
float utilization = actual_bw / peak_bw_gbps * 100;
printf("BW utilization: %.1f%%\n", utilization);
```

---

## Performance report template

```cpp
void PrintPerfReport(float comp_us, float pipe_us, size_t data_bytes, int nranks)
{
    float comm_est_us = pipe_us - comp_us;
    float speedup = (comp_us + comm_est_us) / pipe_us;
    float overlap_pct = (1.0 - (pipe_us - std::max(comp_us, comm_est_us))
                              / std::min(comp_us, comm_est_us)) * 100;

    size_t rs_bytes = (nranks - 1) * data_bytes / nranks;
    size_t ag_bytes = rs_bytes;
    float rs_bw = rs_bytes / (comm_est_us * 0.5 * 1e-6) / 1e9;
    float ag_bw = ag_bytes / (comm_est_us * 0.5 * 1e-6) / 1e9;

    printf("=== Performance Report ===\n");
    printf("Compute-only:   %.1f us\n", comp_us);
    printf("Pipelined:      %.1f us\n", pipe_us);
    printf("Comm estimate:  %.1f us\n", comm_est_us);
    printf("Speedup:        %.2fx\n", speedup);
    printf("Overlap:        %.1f%%\n", overlap_pct);
    printf("RS bandwidth:   %.1f GB/s\n", rs_bw);
    printf("AG bandwidth:   %.1f GB/s\n", ag_bw);
}
```

---

## Profiling method

### Host side Event timing

```cpp
aclrtEvent start, end;
aclrtCreateEvent(&start);
aclrtCreateEvent(&end);

aclrtRecordEvent(start, computeStream);
launchCompute(..., computeStream);
launchComm(..., commStream);
aclrtRecordEvent(end, computeStream);
aclrtSynchronizeStream(commStream);
aclrtSynchronizeStream(computeStream);

float total_ms;
aclrtEventElapsedTime(&total_ms, start, end);
```

### Compute-only Baseline

```cpp
for (int i = 0; i < COMPUTE_ONLY_ITERS; i++) {
    aclrtRecordEvent(start, computeStream);
    launchComputeOnly(..., computeStream);
    aclrtRecordEvent(end, computeStream);
    aclrtSynchronizeStream(computeStream);
    float ms;
    aclrtEventElapsedTime(&ms, start, end);
    comp_times.push_back(ms);
}
float avg_comp = median(comp_times);
```

### Sequential Baseline

```cpp
aclrtRecordEvent(start, stream);
launchCompute(..., stream);
aclrtSynchronizeStream(stream);
launchComm(..., stream);
aclrtRecordEvent(end, stream);
aclrtSynchronizeStream(stream);
float seq_ms;
aclrtEventElapsedTime(&seq_ms, start, end);
```

---

## Performance iteration strategy

```
1. Establish baseline (compute-only + sequential)
2. Measuring pipelined performance
3. Calculate speedup and overlap%
4. If overlap < 80%:
   a. Check if communication starts too early (queue idling)
   b. Check whether communication starts too late (Tile is too large)
   c. Check Block load balancing
5. If bandwidth utilization < 60%:
   a. Increase Tile to reduce the number of transmissions
   b. Use pingpong double buffering
   c. Check data alignment
6. Repeat optimization iterations
```

---

## msprof integration

For more in-depth profiling, use `msprof` to collect the hardware timeline:

```bash
# Collect kernel execution timeline
msprof --output=./prof_data --application="mpirun -np 8 ./my_operator"

# Analyze results
msprof --export=timeline --output=./prof_data
```

`msprof` can display the MTE2/MTE3/Cube/Vec pipeline occupancy rate of each AICore and help locate overlapping holes.
