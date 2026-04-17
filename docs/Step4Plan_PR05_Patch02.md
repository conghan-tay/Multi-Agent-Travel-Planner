## Plan: Switch Budget Validation Task to `output_pydantic=BudgetContextPayload`

### Summary
Refactor `validate_budget_context_task` to use CrewAI-native Pydantic task output instead of manual JSON parsing. The validator task will emit `BudgetContextPayload` directly, and flow initialization will consume this typed object for strict fail-fast validation.

### Key Changes
- **Task contract refactor**
  - In [crew.py](/Users/conghantay/Desktop/Contract/MultiAgentSystem/agents/budget/crew.py), set:
    - `output_pydantic=BudgetContextPayload` on `validate_budget_context_task`.
  - Keep prompt instructions aligned with schema fields, but remove “JSON extraction” wording that assumes raw parsing.

- **Remove manual parsing path**
  - Delete `_extract_json_object(...)` and any associated raw JSON parsing/error branches.
  - Update `_validate_plan_context(...)` to:
    - execute validator crew,
    - read typed output from task result (`TaskOutput.pydantic`),
    - assert it is `BudgetContextPayload`,
    - raise explicit validation error if typed output is missing.

- **Flow initialization integration**
  - Keep `initialize()` logic unchanged in behavior:
    - strict fail-fast on invalid/missing payload,
    - deterministic `current_total_estimate` via transport tool,
    - required origin/destination + single flight/hotel price contract.
  - Ensure exceptions now reference task output parsing as “typed output missing/invalid” rather than “invalid JSON”.

- **Doc touch-up**
  - In [README.md](/Users/conghantay/Desktop/Contract/MultiAgentSystem/README.md), keep CLI contract text as-is, optionally add one short developer note that validation uses CrewAI `output_pydantic` strict schema enforcement (if desired).

### Test Plan
- **Update existing budget validation tests**
  - Adjust tests that assumed manual JSON extraction internals.
  - Add/assert that `_validate_plan_context(...)` returns `BudgetContextPayload` from task typed output.
- **New focused tests**
  - Valid typed output path: task returns `pydantic=BudgetContextPayload`, flow proceeds.
  - Missing typed output path: task output exists but `pydantic=None` -> strict validation error.
  - Wrong typed output path: non-`BudgetContextPayload` object -> strict validation error.
- **Regression tests**
  - Re-run budget flow router tests for fail-fast and deterministic baseline behavior.
  - Re-run full suite to ensure no regressions outside budget module.

### Assumptions
- Current pinned `crewai` version (`1.12.2`) continues to support `Task.output_pydantic` and `TaskOutput.pydantic`.
- Strict schema mode remains required (no heuristic fallback reintroduced).
- No change to public CLI contract beyond internal validation plumbing.
