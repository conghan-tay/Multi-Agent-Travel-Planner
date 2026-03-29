### Step 3 Plan (Revised) — Single `FlightHotelScoutCrew` with 2 Async Tasks + Sequential Merge

### Summary
Implement Step 3 with **one crew** containing three tasks:
1. `search_flights_task` (`async_execution=True`)
2. `search_hotels_task` (`async_execution=True`)
3. `merge_results_task` (sequential fan-in, depends on both via `context=[search_flights_task, search_hotels_task]`)

Use `kickoff_async()` for execution. Flight/hotel tasks run concurrently; merger runs only after both complete.

### Key Changes
- Add `agents/scout/crew.py` with `FlightHotelScoutCrew`:
  - One `Crew(process=Process.sequential, ...)`.
  - Flight and hotel tasks marked `async_execution=True`.
  - Merge task consumes both outputs in context and calls `calculate_total_cost(flight_price, hotel_total, num_travelers)`.
  - `run_async(user_request: str)` as primary async runner.
  - `run(user_request: str)` sync wrapper.
- Add `agents/scout/tools.py` transport wrappers:
  - `search_flights_tool`, `search_hotels_tool`, `calculate_total_cost_tool`.
  - Same error-wrapping pattern as itinerary tools.
- Add CLI: `agents/scout/__main__.py`
  - `python -m agents.scout "<natural-language request>" [--verbose]`.
  - Same parse/error/exit style as itinerary CLI.
- Keep fail-fast behavior on async/runtime errors (no hidden sequential fallback).
- Ensure merger output returns top 3 value-ranked packages and one final recommendation.

### Test Plan (Lean, Deterministic)
- `tests/test_scout_crew_config.py`
  - Assert 1 crew, 3 tasks, correct task names.
  - Assert `search_flights_task.async_execution is True`.
  - Assert `search_hotels_task.async_execution is True`.
  - Assert `merge_results_task.context` includes both async tasks.
- `tests/test_scout_tools.py`
  - Wrapper call mapping and transport connectivity error wrapping.
- `tests/test_scout_cli.py`
  - Parse args and success/failure exit behavior with mocked crew.
- `tests/test_scout_async_orchestration.py`
  - Mock task/crew execution path to verify merge runs after both async task outputs are available.
- Manual check
  - Run with `--verbose`; confirm near-simultaneous flight/hotel start and merge after both complete.

### Public Interface Additions
- New CLI command: `python -m agents.scout "<request>" [--verbose]`
- New class:
  - `FlightHotelScoutCrew(verbose: bool = False)`
  - `run(user_request: str) -> str`
  - `run_async(user_request: str) -> str`

### Assumptions
- Input remains natural-language (no structured params API in this step).
- Tool contract is the implemented one: `calculate_total_cost(flight_price, hotel_total, num_travelers)`.
- Step 3 remains isolated from A2A/orchestrator/cooldown/session-state work.
