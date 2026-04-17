## Step 4 Plan: `BudgetOptimizerCrew` Flow + Plan-Context Validation

### Summary
Implement Step 4 as a new `agents.budget` specialist using CrewAI Flow (`@start`, `@listen`, `@router`) with max 3 optimization iterations and explicit budget-stop conditions.  
Add pre-loop validation so requests to `agents.budget` fail fast with a clear validation error when plan/package context is missing, including your required minimum input rule.

### Implementation Changes
1. **Add new budget specialist package**
- Create `agents/budget/{__init__.py,tools.py,crew.py,__main__.py}`.
- Add `pricing-db-tools` wrappers in `tools.py` (`lookup_avg_price_tool`, `get_budget_tiers_tool`) following existing itinerary/scout wrapper style and connectivity error handling.
- Add CLI entrypoint: `python -m agents.budget "<request>" [--verbose]` with same exit/error conventions as current agents.

2. **Implement Flow-based loop with router**
- In `crew.py`, define `BudgetOptimizerState` (destination, target_budget, current_cost, current_plan, iteration_count, max_iterations, savings_log, validation context).
- Build `BudgetOptimizerFlow(Flow[BudgetOptimizerState])` with:
  - `@start()` preflight initialization and validation pass.
  - analysis step (BudgetAnalysisAgent + pricing tools).
  - adjustment step (PlanAdjustmentAgent + pricing lookup tool).
  - `@router(...)` budget check returning continue/stop path.
  - loop continuation path until either:
    - `current_cost <= target_budget`, or
    - `iteration_count == 3`.
- Expose wrapper class `BudgetOptimizerCrew` with `run(user_request: str) -> str` that kicks off the flow and returns final output text.

3. **Add plan-context validation behavior (your addition)**
- Validation mode: **LLM-based** preflight validator (as selected), run before optimization.
- Input mode: **natural language only** (`user_request`), no required JSON/flags.
- Validation contract:
  - Accept if request includes either:
    - minimum concrete context: current flight option(s), hotel option(s), trip length/dates, traveler count, **or**
    - a pasted itinerary/package summary with enough detail to derive those fields.
  - If missing, return a structured validation error message:
    - clearly says plan context is required,
    - lists required minimum fields,
    - does not run analysis/adjust loop.
- Initial `current_cost` default (when no explicit total): **best-value baseline** from provided options and traveler count.

4. **Update docs and command guidance**
- Update README “implemented scope” and usage sections to include Step 4 direct-run command and expected behavior (validation fail-fast + 2–3 loop iterations on tight budgets).

### Public Interfaces / Type Additions
- New CLI:
  - `python -m agents.budget "<budget optimization request>" [--verbose]`
- New class API:
  - `BudgetOptimizerCrew(verbose: bool = False)`
  - `BudgetOptimizerCrew.run(user_request: str) -> str`
- New internal flow state model:
  - `BudgetOptimizerState` with iterative budget fields and validation context fields.

### Test Plan
1. **Budget tools tests**
- Wrapper delegation arg mapping for `lookup_avg_price` and `get_budget_tiers`.
- Connectivity error wrapping when pricing server is unreachable.

2. **Budget crew/flow config tests**
- LLM provider/model resolution parity with existing crews.
- Flow wiring assertions: start method, analysis/adjust methods, router existence, max iteration handling.

3. **Router and loop behavior tests (deterministic via monkeypatch)**
- Stops immediately when budget already met.
- Continues when over budget and stops at iteration 3 when still over.
- Updates state (`current_cost`, `iteration_count`, `savings_log`) each cycle.

4. **Validation tests**
- Rejects insufficient context with required-field error message.
- Accepts request with explicit fields.
- Accepts pasted itinerary/package-summary style input.
- Ensures no optimization steps run when validation fails.

5. **CLI tests**
- `parse_args` with `--verbose`.
- `main()` success and failure exit codes via mocked `BudgetOptimizerCrew`.

### Assumptions and Defaults
- Step 4 remains direct specialist execution only (no A2A/orchestrator/cooldown/session-state changes in this step).
- Validation uses LLM preflight classification/extraction, but tests stay deterministic by mocking validator output.
- Validation error will explicitly require: flight option(s), hotel option(s), trip length/dates, traveler count, or pasted itinerary/package summary.
