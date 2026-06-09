# AKO4PTO Task — PTO operator optimization

PTO operator optimization tasks applicable to both **PTO-DSL** (Python) and **PTO-tile-lib** (C++) scenarios.

## Skill relationship

This skill relies on the **PTO Costmodel query skill** in the same directory:

- **`pto-costmodel-query-pto-cycles`** — Query the number of simulation cycles of a single PTO ISA instruction
  - Path: `agents/skills/pto-costmodel-query-pto-cycles/SKILL.md`
  - Purpose: In optimization iterations, use costmodel to analyze the cycle cost of PTO instructions under different tile shapes/parameter configurations to guide the optimization direction.
  - Typical usage: `python3 tools/query_pto_cycles.py TMATMUL half half float --m 128 --k 64 --n 128`
  - Capability: Single PTO ISA instruction level cycles simulation (TMATMUL, TADD, TEXP, etc.), pure CPU operation, no real hardware required
  - Limitations: Operator-level (multi-instruction combination) simulation is not supported

This skill (`pto-costmodel-agentic-kernel-optimization`) will call costmodel during the iteration process:
1. Compare the instruction cycle overhead under different tile parameters
2. Verify optimization assumptions (such as "larger tiles have lower TMATMUL per FLOP cycle")
3. Guide the direction of parameter search and reduce blind trial and error.

## Scope of application

| Dimension | PTO-DSL (Python) | PTO-tile-lib (C++) |
|------|------------------|---------------------|
| Build method | Python JIT (`wrapper._build()`) | CMake + `make -j16` + Bisheng |
| Parameter adjustment method | Python environment variables/kernel parameters | C++ template parameters, `.h` constants, `.cpp` internal parameters |
| Benchmark | Python benchmark script → `report.json` | Compile binary → `report.csv` (duration_us, TFLOPS) |
| Code location | `.py` under `workspace/pto-kernels/` | `.cpp`/`.hpp` under `workspace/kernel/` |
| Correctness | `correctness.passes` in `report.json` | Built-in `ResultCmp` output "test success"/"test failed" |
| Typical operators | `flash_attention_score`, `ffn`, etc. | `fa_performance`, etc. |

The Agent will automatically determine which scenario it belongs to based on the operator source code provided by the user, and select the corresponding construction and benchmark process.

---

## First principles

PTO operator optimization is not a general code tidying up, but a hardware-oriented bottleneck elimination process.

Every optimization must be able to answer the following four questions, otherwise do not change the code:

1. What is the current bottleneck?
2. Why does this change work on Ascend?
3. Which indicator is expected to improve?
4. How to ensure correctness

A good PTO optimization is: **correct, measurable, repeatable, bottleneck-driven, hardware-based, and maintainable enough to be retained**. No pursuit of ingenuity, complexity, or theoretical elegance.

---

## Main process

Execute in the following order.

### 1. Confirm the optimization operator

**Must** confirm with the user the operator to be optimized. There are two ways:

- **The user directly gives the operator source code path** (such as `/path/to/flash_atten/`)
- **Agent scans known paths**: Searches the directory in the project or specified by the user, finds operators that can be optimized, and lists them for the user to choose.

After confirming the operator, the Agent should quickly browse the source code and **automatically determine** whether it is PTO-DSL or PTO-tile-lib type:
- Contains `.py` kernel definition + `pto_kernels` / `ptodsl` related import → PTO-DSL
- Contains `CMakeLists.txt` + `.cpp`/`.hpp` + PTO tile macro → PTO-tile-lib

Confirm the judgment results with the user.

### 2. Confirm optimization Case

**Must** confirm with the user the specific case configuration of this optimization:

- **Shape**: such as `S=32768, HEAD_SIZE=128, BATCH=1` (sequence length, head dimension, etc.)
- **Dtype**: such as `float16`, `bfloat16`
- whether a causal mask is used
- Other special configurations

If the operator has multiple testable cases, list the options for the user to choose.

### 3. Confirm the remote environment and Costmodel

Confirm with the user:
1. Remote server connection method (which connect skill to use)
2. Whether to use costmodel, costmodel tool path
3. The operator’s remote deployment path (if it already exists)

### 4. Automatically create project workspace

After obtaining the above information, Agent **automatically** creates the project workspace without manual operation by the user:

```bash
# Copy infrastructure from project_template/
mkdir -p projects/<operator_name>/
cp -r project_template/* projects/<operator_name>/

# Create necessary directories
mkdir -p projects/<operator_name>/{context,runs,workspace}

# Copy the operator source code to the isolated workspace
# PTO-DSL: copy to workspace/pto-kernels/
# PTO-tile-lib: copy to workspace/kernel/
cp -r <source_path> projects/<operator_name>/workspace/<pto-kernels|kernel>/
```

After creation is complete:
- Based on the case information provided by the user, **automatically generate** `TASK_REQUIREMENTS.md` (including operator name, case configuration, adjustable parameters, etc.)
- Confirm with the user whether the `context/` reference and `TASK_REQUIREMENTS.md` need to be modified

### 5. Read task context

Read this before starting:
- `projects/<operator_name>/TASK_REQUIREMENTS.md`
- `projects/<operator_name>/context/`
- Remote connection skills (`connect-server`, `remote.md`, etc.)
- All source code related to the target operator under `projects/<operator_name>/workspace/`

Before entering into tuning, at least make sure:

| Dimension | PTO-DSL | PTO-tile-lib |
|------|---------|--------------|
| Entry function | kernel spec path | Entry template function (such as `LaunchTFA<...>`) |
| Tunable parameters | Python environment variables / kernel parameters | C++ template parameters / `.h` constants / `.cpp` internal parameters |
| benchmark command | Python benchmark script | `./fa_performance --npu=0 --cases="..."` |
| Correctness judgment | passes field in `report.json` | "test success" / "test failed" |
| Performance indicators | duration_ms / TFLOPS in `report.json` | duration_us / TFLOPS in `report.csv` |
| Build command | `wrapper._build()` | `cmake + make -j16` |

### 6. Open the remote link

If the remote environment is accessed for the first time, the first priority is not tuning, but bringing the environment to the point where it can run the benchmark stably.

Only when the following conditions are met can the real performance iteration be entered:

**PTO-DSL**:
1. SSH connection successful
2. The remote working directory has been established and the isolation workspace has been uploaded.
3. Remote Python path and version confirmed
4. At least successfully run a valid `report.json`, and confirm that both baseline and pto have benchmark ok + correctness passes

**PTO-tile-lib**:
1. SSH connection successful
2. The remote working directory has been established
3. The Bisheng compiler, CANN, and ACL runtime are installed remotely
4. Successfully complete at least one full build (`cmake + make`)
5. Successfully run at least one valid result: no errors in the build + "test success" + `report.csv` has valid data

If any of the above is not satisfied, this round should be regarded as an "environment clearing round", and priority should be given to repairing the environment instead of rushing to change the kernel.

### 7. Run torch_npu Baseline

**Before starting the optimization iteration**, you must first run a copy of the baseline performance data of `torch.nn.functional.scaled_dot_product_attention` (or the PyTorch standard implementation corresponding to the operator) as a reference for the final comparison.

Run the PyTorch benchmark on the remote server:
- Use the same shape and dtype configuration as the optimization case
- At least 5 warmups + 10 times for timing
- Record avg, min, max duration and TFLOPS
- credited to torch_npu baseline section of `ITERATIONS.md`

### 8. Enter performance iteration

Before starting tuning in each new session, you must first:
1. Understand the current best results
2. Understand recent failed assumptions
3. Continue from the best known state, don’t blindly start from scratch
4. Refer to `projects/<operator_name>/context/` and `TASK_REQUIREMENTS.md`

Then execute according to the **Optimization Rules** and **Iteration Protocol** below.

---

## Build and run process

### PTO-DSL (Python)

```bash
# Build
python3 -c "from pto_kernels import <kernel>; wrapper._build()"

# Benchmark
python3 bench_<kernel>.py --case "<shape_config>"
```

### PTO-tile-lib (C++)

```bash
# Build
cd workspace/kernel/
rm -rf build && mkdir build && cd build
python3 ../scripts/generate_cases.py --cases "<case_config>" --qk-preload <N>
cmake -DRUN_MODE=npu -DSOC_VERSION=Ascend910B1 ..
make -j16

# Benchmark
python3 ../scripts/gen_data.py --cases "<case_config>"
./fa_performance --npu=0 --cases "<case_config>"
```

---

## Optimization rules

### One hypothesis per round

Only **one** hypothesis is tested per iteration. All code/parameter modifications must serve the same assumption.

### Correctness comes before performance

Each round must be executed in order: modify code/parameters → build → run correctness test → run performance test only after passing.

- Correctness failed → Performance result is invalid, record and terminate this round
- No tolerance allowed (unless explicitly approved by the user)
- Modification of benchmark workload or verification logic to "increase scores" is not allowed

### Editable range

By default, only the operator kernel source code and closely related parameter configurations are allowed to be modified.

Do not modify benchmark scripts, run harnesses, test logic, correctness thresholds, or workload shapes unless there is a clear bug. Never "improve" a benchmark by making it easier.

### Forced bottleneck classification

Before each code change, the current bottleneck must be classified as one of the following:

| Category | Description |
|---|---|
| GMEM traffic bound | Global memory bandwidth bottleneck |
| UB / tile buffer pressure | UB buffer pressure |
| small-transfer inefficiency | small packet transmission inefficiency |
| compute under-utilization | Insufficient utilization of computing power |
| AIC/AIV imbalance | Cube/vector imbalance |
| pipeline bubble / poor overlap | pipeline bubble / insufficient overlap |
| barrier / wait / sync overhead | synchronization overhead is too large |
| register pressure / occupancy loss | register pressure / occupancy loss |
| bad tile shape | tile bad shape |
| dependency chain too long | dependency chain too long |
| CV FIFO pressure | Cube-Vector FIFO congestion |
| unknown | Unknown - must check code and profiling data first |

### Ascend Hardware Checklist

Before starting each round, you must check each item:

**Tile shape** — Tile rationality, computing unit filling rate, tail overhead, UB usage

**GM ↔ UB handling** — total handling times, redundant reload/store-back, continuity, reuse rate

**Small packet risk** — Fragmented copy, whether the output of each tile is too small, whether the shape destroys the transmission efficiency

**Barrier/wait/sync** — Amount, whether to serialize unnecessarily

**UB pressure** — tile buffer + FIFO buffer + temporary buffer total occupation

**Pipeline overlap** — Whether the overlap of each stage is sufficient

**AIC/AIV Balancing** — Whether the loads on the cube and vector sides are balanced

**Bottleneck transfer risk** — Is the bottleneck simply transferred rather than eliminated?

### Optimization priority (from high to low)

1. **Eliminate unnecessary data transfer** - Reduce redundant GM load/store and improve UB reuse
2. **Correction of unreasonable tile shape** — Improve tile dimensions to improve utilization and handling efficiency
3. **Reduce inefficiency of small packet transmission** — merge or batch small packet transmission
4. **Improve load/compute/store overlap** — Improve steady-state pipeline overlap
5. **Reduce barrier/wait overhead** — Remove barriers that prove to be useless
6. **Reduce UB/register pressure** — shorten the live range and reduce the temporary buffer that is not conducive to overlap
7. **Improve command organization** — Reorganize calculations to improve AIC/AIV balance
8. **Fine-tuning will only be done after all the above problems are solved**

### High risk changes

The following changes are considered high risk and require additional justification:

- Larger tiles may cause UB to explode or compile to fail
- Modifying the FIFO size may change kernel semantics
- Lack of dependency proof before removing barrier
- Instruction rearrangement may change numerical behavior
- "potentially faster" changes with no hardware justification

### Prohibited Behavior

1. Make multiple unrelated changes in one round
2. Skip correctness testing
3. Claim victory from a single noise measurement
4. Modify the benchmark workload or weaken the verification logic to improve the numbers
5. Do massive rewrites without evidence of bottlenecks
6. Continue random trial-and-error after multiple failures
7. Hide failed experiments
8. Optimize for code beauty, not for hardware bottlenecks
9. Declare success based on theoretical reasoning alone

### Three rounds of failure rules

If there is no substantial benefit for 3 consecutive rounds, blind local fine-tuning must be stopped:

1. Recheck the current bottleneck classification
2. Check if previous rounds were attacking the symptoms rather than the root cause
3. Find different optimization directions
4. Prioritize structural changes
5. You can search for relevant information and references online

---

## Iteration protocol

Each "code modification or parameter adjustment to verify performance" plus "a build and benchmark execution" are counted together as one iteration. The iteration numbers increase sequentially: `0, 1, 2, ...` (iter-0 is baseline).

After each round, you must do the following:

1. Save under `projects/<operator_name>/runs/iter-XXX/`:
   - `files.txt` — list of files modified in this round
   - `patch.diff` — current round of code diff
   - `notes.md` — detailed records of this round
2. Add a simple summary line to `projects/<operator_name>/ITERATIONS.md`

### patch.diff record rules

- **Code modification class iteration**: standard `diff -u` format
- **Adjustment parameter class iteration**:
```
# This round is the parameter adjustment class iteration
# Parameter changes:
-  PARAM=old_value
+  PARAM=new_value
# Configuration based on iter-XXX
```

### Benchmark Discipline

- **Same workload**: The same case must be used for comparison before and after
- **Repeatability**: Important performance results must be run multiple times
- **Noise processing**: Noisy data is marked as `inconclusive`
- **Victory Judgment**: Correctness passed + same workload + improvement repeatable + benefit greater than noise

### Result determination

- `kept`: The result is correct and better than the current best known result
- `neutral`: the result is correct, but not better than the current frontier result
- `failure`: The result is wrong, compilation fails, or this round of experiment is invalid
- `inconclusive`: data fluctuates greatly, rerun to confirm

---

## notes.md logging requirements

### Pre-Edit (fill in before changing the code)

- **Kernel**: target operator name and current configuration
- **Current bottleneck**：
- **Evidence**：
- **Hypothesis**：
- **Why it should help on Ascend**：
- **Expected improved metric**：
- **Main risk**：

### Changes (fill in after changing the code)

- **Modification type**: code modification/template parameter adjustment/environment variable/build configuration
- **Modified files**: List all modified file paths
- **Specific changes**: State the old value → new value of each parameter, or the specific content of the code modification
- **Complete parameter snapshot**: All parameter configurations of this round (easy to reproduce)

### Post-Run (fill in after running the benchmark)

- **Correctness**：pass / fail
- **Performance**: Specify specific values (duration, TFLOPS, etc.)
- **Stability**：stable / noisy
- **Result**：kept / neutral / failure

### Analysis

Detailed analysis of why it works or fails.

### Next

What to try next round.

### Additional records for the environment clearing round

Remote environment version information, whether the build was successful, the first effective result path, and major pitfalls.

---

## Closing requirements

After the optimization is completed, a summary comparison picture (PNG) must be generated. The style refers to `projects/flash_attention/summary.png`.

### Chart structure: upper and lower double charts

**Upper half—improvement multiple line chart**:
1. Y-axis: speedup multiple (x) relative to initial PTO
2. Polyline: actual speedup in each round (green) + best frontier (orange)
3. Scatter marks: green=kept, blue=neutral, red cross=failure
4. **Stage background color**: Different optimization stages are distinguished by different color backgrounds (such as baseline / costmodel-guided / parameter verification / fine-tune)
5. **Milestone Marking**: Key improvement points are marked with specific changes.
6. Top summary: total iterations, kept/neutral/failure statistics, final speedup, comparison with torch_npu

**Bottom Half - Absolute Latency Histogram**:
1. Y axis: duration (us or ms, log scale can be used if necessary)
2. Histogram color distinction: gray=baseline, green=kept, blue=neutral, red=failure
3. torch_npu reference line (purple dotted line)
4. Mark each column with a specific value.

**Bottom**: Text description torch_npu / PTO initial / PTO best values and key conclusions

### Iterative simplification

If the total number of iterations is large (>10), the X-axis only shows the key iterations: baseline, each kept, typical failure, and final best. Condensing consecutive neutrals/failures into one or two representative ones without showing them one by one.

Save to `projects/<operator_name>/summary_chart.png`.
