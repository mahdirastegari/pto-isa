# AKO4PTO

This is a multi-project workspace for PTO operator tuning.

Goal:

- Do not pollute the original `pto-kernels` directory
- Different operators use independent project directories
- Modify code in isolated copies of respective projects
- Perform benchmark verification through remote Ascend environment
- Keep complete records of each round of tuning

## Suggested reading order

1. `README.md`
2. `task.md`
3. `remote.md`
4. `project_template/`

## Directory description

- `projects/`: an independent project directory for each operator
- `project_template/`: template used when creating a new operator project
- `task.md`: task process common to all projects
- `remote.md`: Shared remote login, synchronization, and benchmark execution processes
- `context/`: optional shared reference material

## Minimum usage process

1. Create an independent project directory under `projects/` for the current operator.
2. Copy `TASK_REQUIREMENTS.md`, `ITERATIONS.md`, `workspace/`, `runs/`, `context/` from `project_template/`.
3. Copy the original `pto-kernels` to `projects/<operator_name>/workspace/pto-kernels` in the project directory.
4. For specific execution, please press the top-level `task.md`, and for remote connection and environment configuration, please press `remote.md`.
5. Modify the code in the project's own `projects/<operator_name>/workspace/pto-kernels`.
6. After each round, write the record to the project's own `runs/iter-XXX/`, and update the project's own `ITERATIONS.md` synchronously.

## Use Agent to automatically search for optimization

If an agent is used to automatically perform tuning, after entering the `AKO4PTO` root directory, the user should directly ask the agent to act according to the top-level `task.md`.
