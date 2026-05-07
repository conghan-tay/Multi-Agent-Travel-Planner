# Step 7/8 Plan: Adapter-Level Cooldown with `before_tool_call`

## Summary
Combine Recommended Build Order Step 7 and Step 8 into one implementation. Instead of adding a Budget-only `before_kickoff` phase and later refactoring it, enforce cooldown for all specialist A2A adapters through CrewAI's `before_tool_call` hook.

## Implementation Changes
- Add a reusable `CooldownGuard` in `guards/cooldown_guard.py`.
- Register one process-wide CrewAI `before_tool_call` hook from `a2a_servers/runtime.py`.
- Scope the global hook with an adapter-tool registry so only registered `run_specialist` adapter tools are affected.
- Apply cooldown per specialist id:
  - `itinerary_specialist`
  - `flight_hotel_specialist`
  - `budget_specialist`
- Use `COOLDOWN_SECONDS` from the environment, defaulting to `60`.
- When a specialist is blocked, rewrite the adapter tool's `user_request` to an internal sentinel. The `run_specialist` tool detects that sentinel and returns:
  - `Cooldown active for {specialist_id}. Try again in {remaining_seconds} seconds.`

## Public Interfaces
- New module:
  - `guards.cooldown_guard.CooldownGuard`
- No HTTP, CLI, Agent Card, or specialist crew contract changes.
- Existing A2A adapter tool contract remains:
  - `run_specialist(user_request: str) -> str`

## Test Plan
- Unit tests cover first-call allow, repeated-call block, expiry, independent specialist keys, and invalid cooldown config.
- A2A runtime tests cover:
  - repeated adapter calls are blocked without invoking the runner
  - different specialists are tracked independently
  - unrelated tools and unregistered adapter tools are ignored
- Regression:
  - `python -m pytest -q`

## Assumptions
- Cooldown state is in-memory and per running A2A server process.
- A failed specialist runner still counts as an invocation because the cooldown is marked before `run_specialist` executes.
- CrewAI `before_tool_call` hooks are global in `crewai==1.12.2`, so local scoping is handled by the adapter-tool registry.
