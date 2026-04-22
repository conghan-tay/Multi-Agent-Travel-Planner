## Step 4 Consolidated Plan (PR05 + Patch01 + Patch02)

### Summary
Consolidate the Step 4 implementation plans into one final-spec document that reflects the final implementation contract (not chronology).

Step 4 remains a direct specialist (`python -m agents.budget`) implemented as a strict, typed, deterministic CrewAI Flow with fail-fast validation and max-3 iteration routing.

### Key Implementation Changes
1. Budget specialist package (`agents/budget`)
- Retain `crew.py`, `tools.py`, `__main__.py`, `__init__.py`.
- Keep direct CLI entrypoint:
  - `python -m agents.budget "<budget optimization request>" [--verbose]`

2. Flow loop contract
- Keep `BudgetOptimizerFlow(Flow[BudgetOptimizerState])` with:
  - `@start()` initialization/validation.
  - analysis step.
  - adjustment step.
  - `@router(...)` stop/continue routing.
- Exit conditions:
  - stop when `current_cost <= target_budget`, or
  - stop when `iteration_count == 3`.

3. Strict typed preflight validation
- `validate_budget_context_task` must use:
  - `output_pydantic=BudgetContextPayload`
- `_validate_plan_context(...)` must consume:
  - `TaskOutput.pydantic` only.
- Remove/avoid manual JSON extraction fallback behavior.
- Fail fast when typed output is missing, wrong type, or schema-invalid.
- Validation input remains natural-language `user_request` only (no required JSON/flags in CLI input).

4. Input contract (single package context)
- Required fields:
  - `origin`
  - `destination`
  - `target_budget`
  - `traveler_count`
  - `trip_nights` or (`start_date` + `end_date`)
  - `flight_price_per_person`
  - `hotel_total`
- Reject missing/invalid/ambiguous values with explicit schema/validation errors.

5. Deterministic baseline cost
- Do not trust LLM `current_total_estimate` as source of truth.
- Compute baseline in code via transport tool:
  - `calculate_total_cost(flight_price, hotel_total, num_travelers)`
- Use returned `grand_total` as canonical initial `current_cost`.

6. Pricing lookup normalization
- LLM-facing budget tools must use constrained wrappers only:
  - `lookup_avg_flight_price(destination)` -> `travel_type="flight"`
  - `lookup_avg_hotel_price(destination, tier)` -> `hotel_budget|hotel_midrange|hotel_luxury`
- Prevent open-ended/invalid `travel_type` values (for example: `accommodations`, `flights`).

7. Adjustment output parsing hardening
- Accept:
  - `New Estimated Total: $X`
  - markdown-label variants (for example `**New Estimated Total**: $X`)
- Fail hard when no parseable numeric final total exists.

8. Documentation updates
- Keep README and CLI guidance aligned with strict single-package Step 4 contract.
- Existing Step 4 plan files remain unchanged for historical traceability.

### Public Interfaces and Contracts
- CLI:
  - `python -m agents.budget "<request>" [--verbose]`
- Python API:
  - `BudgetOptimizerCrew(verbose: bool = False)`
  - `BudgetOptimizerCrew.run(user_request: str) -> str`
- Validation contract:
  - strict typed schema via `BudgetContextPayload`
  - fail-fast behavior
  - no heuristic fallback path
- Scope:
  - direct specialist mode only (no Step 5+ A2A/orchestrator/cooldown/session-state behavior in this step)

### Test Plan
1. Validation schema tests
- Valid complete payload passes.
- Missing `origin` or `destination` fails.
- Invalid numeric/date/trip-length consistency fails.
- Missing typed output (`pydantic=None`) fails.
- Wrong typed output object type fails.

2. Deterministic baseline tests
- Baseline uses transport tool `grand_total`.
- LLM `current_total_estimate` mismatch does not override canonical baseline.

3. Flow/router behavior tests
- Immediate stop when already within budget.
- Continue while over budget.
- Hard stop at 3 iterations when still over.
- State updates across loop (`iteration_count`, `current_cost`, `savings_log`).

4. Pricing wrapper tests
- Budget agents no longer use invalid raw travel-type strings.
- Wrapper mappings call only valid `travel_type` values.

5. Output parse robustness tests
- Parse plain `New Estimated Total: $3000`.
- Parse markdown `**New Estimated Total**: $3000`.
- Fail when no numeric final total exists.

6. CLI tests
- `parse_args` with `--verbose`.
- `main()` success/failure exit behavior with mocked `BudgetOptimizerCrew`.

### Assumptions and Defaults
- This file is a clean final spec (no patch chronology section).
- Pinned CrewAI supports `Task.output_pydantic` and `TaskOutput.pydantic`.
- `transport-tools` and `pricing-db-tools` external contracts remain unchanged.
