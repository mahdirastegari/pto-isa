# Task Requirements

Write here additional requirements for the current task.

Examples of content you can write include:

- Specify the default test shape, for example `BNSD=1,16,8192,512`
- Specify the input size that must be prioritized for optimization
- Specify files or modules that are not allowed to be modified
- Specify behavioral constraints that must be preserved
- Specify the performance indicators of special concern for this task

Example:

```text
- Change the default size to BNSD=1,16,8192,512
- Prioritize torch_npu baseline comparison
- Do not change operators unrelated to flash_attention_score
```

## Hints

<!-- Add directives below, for example:
- Operator-specific constraints or banned settings
- Remote host caveats
- Strategies to try or avoid
- Agent behavior controls
- Dependency policies (e.g., "Do not install any packages") -->

- Prefer small, isolated kernel changes. Treat correctness failure as a hard stop for that iteration.
- If 3 consecutive iterations show no improvement, re-read `../../remote.md`, inspect previous rounds in `ITERATIONS.md`, search online for additional optimization ideas, and re-evaluate the tuning direction before continuing.
