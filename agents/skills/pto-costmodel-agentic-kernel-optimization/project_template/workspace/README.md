# Workspace description

`workspace/` is used to store a copy of the PTO code actually modified by the current operator project.

Principles:

- Only modify the code here
- Do not directly modify the original `pto-kernels` directory
- A project only serves one operator

## Initialization method

Copy the original code to:

```bash
workspace/pto-kernels
```

Example:

```bash
cp -R <original_pto_kernels_path> ./workspace/pto-kernels
```
