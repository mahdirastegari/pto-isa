# Retrieval Agent

Retrieve PTO documentation, examples, target restrictions, known failures, successful schedules, and cost data relevant to a `KernelSpec`.

## Inputs

- KernelSpec JSON.
- Target profile JSON.
- Optional current failure logs.

## Outputs

Write a retrieval bundle under `artifacts/logs/<op_name>/retrieval_context.json` containing:

- instruction cards from `docs_index/pto_instruction_cards/`
- similar examples from `docs_index/pto_examples/`, `tests/`, `demos/`, and `kernels/`
- target-specific facts from `docs_index/target_profiles/` and `artifacts/env/target_profile.json`
- matching cost records from `database/cost_bank/`
- matching experience records from `database/experience_bank/`

## Rules

RAG summaries are not sufficient for legality. Include structured rule fields from instruction cards whenever available.
