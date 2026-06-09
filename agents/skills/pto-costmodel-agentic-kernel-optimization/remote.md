---
name: ako4pto-remote-bringup
description: Remote Ascend environment bring-up for AKO4PTO. Covers SSH connection, workspace upload, Python selection, dependency installation, environment self-test and benchmark verification.
---

# AKO4PTO Remote Environment Bring-Up

## Overview

Bring the remote Ascend machine to a state where it can stably run the target PTO benchmark. Covers two situations: rapid reuse of existing environments and bring-up of empty environments from scratch.

This document is only responsible for remote environment preparation and troubleshooting. The tuning process and iteration protocol are subject to `task.md`.

> [!NOTE]
> `<user>`, `<remote_ip>`, `<path_to>` are provided by the user at the beginning of each session, do not hardcode.

## Workflow

### 1. Confirm SSH

```bash
ssh -o BatchMode=yes <user>@<remote_ip> "echo ssh_key_ok"
```

### 2. Local preparation workspace

After confirming the local path of `pto-kernels` with the user, **first make sure locally** that the four dependent libraries under `external/src/` are complete:

```bash
cd <pto-kernels path>
ls external/src/pto-dsl external/src/PTOAS external/src/pto-isa external/src/ops-transformer
```

If missing, it will be completed locally:

```bash
bash scripts/bootstrap_workspace.sh
```

In this way, `external/src/` will be transferred to the remote during subsequent uploads to avoid remote git clone being affected by the network.

### 3. Upload workspace

The remote directory structure remains consistent with the local one. Upload command (scp is preferred, rsync is optional):

```bash
# preferred
scp -r projects/<operator_name>/workspace/pto-kernels <user>@<remote_ip>:<path_to>/AKO4PTO/projects/<operator_name>/workspace/

# Alternative (incremental synchronization)
rsync -avz projects/<operator_name>/workspace/pto-kernels/ <user>@<remote_ip>:<path_to>/AKO4PTO/projects/<operator_name>/workspace/pto-kernels/
```

### 4. Identify remote Python

```bash
which python3 && python3 --version
```

- Do not assume that system `python3` satisfies PTO dependencies and do not replace system Python
- If the remote default is `Python 3.9`, user mode `Python 3.11` is preferred (such as `~/.local/miniforge3/envs/pto-py311/bin/python`)
- Once an interpreter is selected, it will be used for all subsequent operations and will not be mixed with system Python.

### 5. Quick reuse (existing environment)

If the remote environment is most likely already set up, do the minimum verification first and don’t rush to install anything:

```bash
cd <path_to>/AKO4PTO/projects/<operator_name>/workspace/pto-kernels
bash scripts/source_env.sh
<python_exec> scripts/check_env.py --strict
<python_exec> -c "import mlir.ir; from mlir.dialects import pto; print('mlir_ok')"
<python_exec> -c "import torch, torch_npu; print(torch.npu.is_available())"
ptoas --version
<python_exec> -m pto_kernels.bench.runner <target_spec>
```

All passed → reuse successfully, go directly to tuning. Any step fails → proceed to full bring-up below (step 6 onwards).

### 6. Confirm remote dependency source code

Step 2 Ensure that `external/src/` is complete locally. Confirm remotely after uploading:

```bash
ls external/src/pto-dsl external/src/PTOAS external/src/pto-isa external/src/ops-transformer
```

If it is missing, `bash scripts/bootstrap_workspace.sh` will be executed remotely.

> [!NOTE]
> `bootstrap_workspace.sh` requires remote access to GitHub / GitCode. No response for more than 10 seconds → scp upload `external/src/` again after local completion.

### 7. Install Python dependencies

```bash
<python_pip> install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
<python_pip> install -i https://pypi.tuna.tsinghua.edu.cn/simple torch-npu==2.8.0.post2 --extra-index-url https://download.pytorch.org/whl/cpu
<python_pip> install -i https://pypi.tuna.tsinghua.edu.cn/simple numpy PyYAML mpmath 'pybind11<3' decorator
```

> [!IMPORTANT]
> **10 seconds timeout rule**: If remote `pip install` or any download command exceeds **10 seconds without response**, immediately Ctrl-C, switch to local download + scp upload:
> ```bash
> pip download -i https://pypi.tuna.tsinghua.edu.cn/simple <package> -d /tmp/wheels/
> scp -r /tmp/wheels/ <user>@<remote_ip>:<path_to>/wheels/
> <python_pip> install --no-index --find-links <path_to>/wheels/ <package>
> ```

### 8. Load environment + check ptoas/mlir

```bash
bash scripts/source_env.sh
ptoas --version
<python_exec> -c "import mlir.ir; from mlir.dialects import pto; print('mlir_ok')"
```

If it fails, you usually need to manually fill in the environment variables:

```bash
export PATH=<py311_bin>:<ptoas_cli_bin>:$PATH
export LD_LIBRARY_PATH=<py311_lib>:<mlir__mlir_libs>:<ptoas_cli_lib>:/usr/local/Ascend/cann-*/aarch64-linux/lib64:$LD_LIBRARY_PATH
```

Note: The `lib` directories of `mlir/_mlir_libs` and `ptoas` CLI must always be placed in `LD_LIBRARY_PATH`.

### 9. Environment self-test + benchmark verification

Execute the same complete verification sequence as step 5 (`check_env.py --strict` → mlir → torch_npu → ptoas → bisheng), and then run the target benchmark:

```bash
<python_exec> -m pto_kernels.bench.runner <target_spec>
```

Whether the environment is available depends on the gate in `task.md`.

## Troubleshooting

- **SSH password required**: Check local private key, remote `authorized_keys`, login username.

- **Existing environment cannot be run**: First confirm the warehouse path, Python path, whether `source_env.sh` is successful, and `check_env.py --strict`. Only move to a full bring-up when it is confirmed that it is irreparable.

- **`torch_npu` import failed**: Check whether the Ascend environment is loaded, whether the Python path is correct, and whether `torch_npu` is installed with the correct interpreter.

- **`torch.npu.is_available()` is False**: Check whether `LD_LIBRARY_PATH` contains CANN `aarch64-linux/lib64` and whether `source_env.sh` exits early.

- **`import mlir.ir` failed**: Check whether the `ptoas` wheel is installed in the current interpreter and whether `LD_LIBRARY_PATH` contains `mlir/_mlir_libs`.

- **`ptoas --version` passes but compilation fails**: Check `PATH` and `LD_LIBRARY_PATH` to see if the ptoas CLI's bin/lib is included.

- **Remote download unresponsive for more than 10 seconds**: Do not retry. Local `pip download` → scp upload → remote `pip install --no-index --find-links` offline installation.
