# Step 6 Plan: Travel Orchestrator A2A Client

## Summary
Implement `TravelOrchestratorCrew` as the root A2A client. The orchestrator delegates to the three specialist A2A servers through `A2AClientConfig` and does not import specialist crew implementations.

## Implementation Changes
- Add `agents/orchestrator` with a single CrewAI orchestrator agent and one routing task.
- Configure three A2A client endpoints:
  - `http://127.0.0.1:9001/.well-known/agent-card.json`
  - `http://127.0.0.1:9002/.well-known/agent-card.json`
  - `http://127.0.0.1:9003/.well-known/agent-card.json`
- Add `python -m agents.orchestrator "<request>" --verbose` and root `python main.py` entrypoints.
- Ensure specialist Agent Cards advertise their JSON-RPC endpoint URL (`/a2a`) while remaining discoverable from `/.well-known/agent-card.json`.
- Keep cooldown and session-state behavior out of this step.

## Public Interfaces
- `TravelOrchestratorCrew(verbose=False).run(user_request: str) -> str`
- `python -m agents.orchestrator "<travel request>" [--verbose]`
- `python main.py "<travel request>" [--verbose]`
- `python main.py` for an interactive REPL.

## Test Plan
- Deterministic tests verify the three `A2AClientConfig` endpoints, no direct specialist crew imports, delegation-only prompt wording, and CLI success/error handling.
- Full regression: `python -m pytest -q`.
- Manual acceptance: start tool servers and specialist A2A servers, then run `python main.py "Plan a 5-day trip to Tokyo for two people"` and confirm routing through `itinerary_specialist`.

## Assumptions
- Routing is LLM-driven from fetched Agent Cards, not hardcoded keyword branching.
- Live delegation requires `make start-tools` and `make start-agents`.
