### Step 5 Plan: A2A Specialist Servers + `make start-agents`

### Summary
Implement Step 5 as **delegation-ready A2A servers** for all three specialists, with a new `make start-agents` process manager and card verification endpoints on ports `9001/9002/9003`.

Because `crewai==1.12.2` does not expose crew-level `a2a` config on `Crew`, we will use the confirmed approach: **thin adapter agents with `A2AServerConfig`** that delegate to the existing specialist crew `run()` methods.

### Implementation Changes
1. Add an A2A server runtime layer (`a2a_servers`) used by all specialists.
- Create one shared server bootstrap module that:
  - Builds an adapter `Agent` with `A2AServerConfig` (`name`, `description`, `skills`, transport defaults).
  - Uses a dedicated tool `run_specialist(user_request: str) -> str` to call the corresponding existing crew.
  - Wires a2a-sdk request handling (`DefaultRequestHandler`) with a small executor bridge that forwards `execute/cancel` to CrewAI A2A task helpers.
  - Exposes a FastAPI app with:
    - `GET /.well-known/agent-card.json`
    - `POST /a2a` (JSON-RPC)
- Keep all A2A runtime config centralized (host/path defaults, common error handling, logging shape).

2. Add three specialist A2A server modules.
- `a2a_servers/itinerary_server.py` -> wraps `ItineraryBuilderCrew.run`, listens on `:9001`.
- `a2a_servers/scout_server.py` -> wraps `FlightHotelScoutCrew.run`, listens on `:9002`.
- `a2a_servers/budget_server.py` -> wraps `BudgetOptimizerCrew.run`, listens on `:9003`.
- Each module exports `app` and a `main()` entrypoint (`python -m ...`) so both `uvicorn` and module execution work.
- Agent Card identity is explicit and stable:
  - `itinerary_specialist`
  - `flight_hotel_specialist`
  - `budget_specialist`

3. Extend Makefile for agent lifecycle management.
- Add `start-agents` (independent from tools, as decided).
- Add agent port check target for `9001/9002/9003`.
- Add PID/log wiring in the same style as `start-tools`:
  - `.pids/*-a2a.pid`
  - `logs/*-a2a.log`
- Extend `stop` to terminate both tool and agent processes cleanly.

4. Documentation updates.
- Update README runtime flow:
  - Step 5 implemented, with exact commands for `make start-agents`.
  - Verification commands for all three Agent Cards.
  - Note that real task delegation requires tool servers running (`make start-tools`).
- Add a new Step 5 plan doc in `docs/` (same style as prior step plan files).

### Public Interfaces / Contracts
- New commands:
  - `make start-agents`
  - `python -m a2a_servers.itinerary_server`
  - `python -m a2a_servers.scout_server`
  - `python -m a2a_servers.budget_server`
- New HTTP endpoints:
  - `http://localhost:9001/.well-known/agent-card.json`
  - `http://localhost:9002/.well-known/agent-card.json`
  - `http://localhost:9003/.well-known/agent-card.json`
  - JSON-RPC task endpoint: `POST /a2a` on each port
- Adapter tool contract:
  - `run_specialist(user_request: str) -> str`

### Test Plan
1. Unit tests (deterministic, no live LLM/tool server required).
- Validate each server module builds app and card metadata (`name`, `description`, `skills`).
- Validate adapter runner wiring calls the intended specialist class/method.
- Validate Makefile target presence/port checks via command-level smoke (non-networked where possible).

2. Local integration acceptance for Step 5.
- `make start-agents`
- `curl http://localhost:9001/.well-known/agent-card.json`
- `curl http://localhost:9002/.well-known/agent-card.json`
- `curl http://localhost:9003/.well-known/agent-card.json`
- Confirm valid JSON cards with correct specialist identity and capabilities.

3. Delegation-ready smoke.
- Send one minimal JSON-RPC task request to each `/a2a` endpoint with a mocked/safe prompt.
- Confirm task reaches completed state and returns agent text output.

4. Regression.
- Run existing pytest suite to ensure Step 1–4 behavior remains unchanged.

### Assumptions
- Step 5 scope is **A2A servers only**; orchestrator (Step 6), cooldown (Step 7/8), and session memory (Step 9) remain out of scope.
- `start-agents` remains independent from `start-tools`; operators run both when executing real specialist work.
- Adapter-agent approach is intentional due current CrewAI API shape and is accepted for this step.
