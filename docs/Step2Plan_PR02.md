## Step 2 Plan — Sequential Itinerary Crew (Lean Incremental PR)

### Summary
Implement only **Recommended Build Order Step 2**: `ItineraryBuilderCrew` as a direct-run specialist (no A2A/orchestrator yet), wired to existing `destination-tools` on `:8001`, with a minimal CLI module entrypoint for manual verification.

### Implementation Changes
1. **Add Step-2 skeleton for direct specialist execution**
- Create the itinerary specialist package with one runnable module (`python -m agents.itinerary "Plan a trip to Paris"`).
- Keep scope limited to itinerary only; do not add scout/budget/A2A code in this PR.
- Reuse existing `.venv` + `requirements.agents.txt`; no Step-1 dependency churn.

2. **Implement `ItineraryBuilderCrew` as strict sequential workflow**
- Define 3 CrewAI agents exactly for this module: Destination Research, Itinerary Draft, Itinerary Formatter.
- Define 3 tasks with explicit context chaining:
  - Research task calls `get_destination_info()` and `get_local_events()`.
  - Draft task consumes only research output and produces day-by-day raw itinerary.
  - Formatter task consumes draft output and returns polished itinerary.
- Enforce sequential process (`Process.sequential`) and deterministic output structure (intro + Day sections + practical notes).

3. **Wire itinerary crew to current tool-server contracts**
- Connect only to `destination-tools` (`:8001`) for Step 2.
- Keep all existing Step-1 tool signatures unchanged.
- Do not modify transport/pricing tools in this step.

4. **Expose minimal run interface + traceability**
- Add a direct-run entrypoint for local testing that accepts one natural-language prompt string.
- Print final itinerary output clearly; support optional verbose mode for debugging task/tool trace.
- Keep implementation small and reviewable (single specialist path, no shared abstraction premature refactor).

5. **Update ops/docs for Step-2 verification**
- Add/adjust run instructions to include:
  - `make install-agents`
  - `make start-tools`
  - `python -m agents.itinerary "Plan a trip to Paris"`
- Document expected behavior: structured itinerary output generated through 3 sequential task stages.

### Public Interfaces / Contracts
- New user-facing command:
  - `python -m agents.itinerary "<travel request>"`
- Step-1 tool-server contracts remain unchanged.
- Step-2 requires `destination-tools` reachable at `http://localhost:8001`.

### Test Plan (Step-2 Acceptance)
1. **Precheck**
- Run `make install-agents`.
- Run `make start-tools` and confirm `curl http://localhost:8001/tools` includes destination tools.

2. **Primary acceptance**
- Run `python -m agents.itinerary "Plan a 5-day trip to Paris in October for 2 people"`.
- Confirm output is produced and includes:
  - destination/event-informed content,
  - day-by-day sections,
  - formatted final itinerary.

3. **Sequential context validation**
- Run with verbose trace enabled.
- Confirm execution order is strictly Research → Draft → Formatter, with downstream tasks consuming prior output.

4. **Failure-path smoke**
- Stop `destination-tools`; rerun itinerary command.
- Confirm clear actionable error (tool server unavailable) without crashing unrelated components.

### Assumptions
- Scope is strictly Step 2 from the PRD build order (sequential itinerary specialist only).
- Current tool contracts are authoritative for this PR; any transport cost-signature alignment is deferred.
- Manual CLI verification is sufficient at this stage (no automated test suite added in this PR).
