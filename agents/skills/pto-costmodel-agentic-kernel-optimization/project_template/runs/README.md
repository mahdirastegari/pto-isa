# Run the product directory

```text
runs/
  _template/
    files.txt
    notes.md
  iter-001/
    files.txt
    patch.diff
    notes.md
```

Each round **must** save three files, no missing files are allowed:

- `files.txt`: List of files modified in this round (parameter adjustment class iteratively writes "environment variable parameter adjustment, passive file modification")
- `patch.diff`: this round of code diff (the parameter adjustment class iteratively writes parameter change instructions, see the format requirements in `task.md`)
- `notes.md`: Detailed records of this round (Pre-Edit/Changes/Post-Run/Analysis/Next)

Fill in after copying from `runs/_template/`.
