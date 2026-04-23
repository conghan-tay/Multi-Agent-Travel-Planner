## Step 5 Plan — A2A Specialist Servers + `make start-agents`

### Summary
Implement Step 5 as delegation-ready A2A specialist servers for itinerary, scout, and budget crews. Add `make start-agents` to run all three A2A servers in background processes and expose Agent Cards on ports `9001`, `9002`, and `9003`.

### Key Implementation Changes
1. Add shared A2A runtime layer (`a2a_servers/runtime.py`)
- Centralize adapter-agent bootstrapping using `A2AServerConfig`.
- Create one shared `run_specialist(user_request: str) -> str` tool contract per server.
- Wire a2a-sdk request handling (`DefaultRequestHandler` + `InMemoryTaskStore`) with an executor bridge that forwards `execute/cancel` to CrewAI A2A task helpers.
- Expose FastAPI endpoints:
  - `GET /.well-known/agent-card.json`
  - `POST /a2a`

2. Add specialist A2A server modules
- `a2a_servers/itinerary_server.py` (port `9001`) wraps `ItineraryBuilderCrew.run`.
- `a2a_servers/scout_server.py` (port `9002`) wraps `FlightHotelScoutCrew.run`.
- `a2a_servers/budget_server.py` (port `9003`) wraps `BudgetOptimizerCrew.run`.
- Each module exports `app` and provides a `main()` entrypoint for `python -m ...`.
- Agent Card identities:
  - `itinerary_specialist`
  - `flight_hotel_specialist`
  - `budget_specialist`

3. Extend Makefile lifecycle commands
- Add `start-agents` (independent from `start-tools`).
- Add `check-agent-ports` for `9001/9002/9003`.
- Add PID/log management:
  - `.pids/itinerary-a2a.pid`, `.pids/scout-a2a.pid`, `.pids/budget-a2a.pid`
  - `logs/itinerary-a2a.log`, `logs/scout-a2a.log`, `logs/budget-a2a.log`
- Extend `stop` to terminate both tool and A2A server processes.
- Add `verify-agent-cards` for endpoint checks.

4. Update docs
- Update `README.md` to mark Step 5 implemented and document:
  - `make start-agents`
  - Agent Card verification commands
  - requirement to run `make start-tools` for real delegated specialist work.

### Public Interfaces / Contracts
- Commands:
  - `make start-agents`
  - `python -m a2a_servers.itinerary_server`
  - `python -m a2a_servers.scout_server`
  - `python -m a2a_servers.budget_server`
- Endpoints:
  - `http://localhost:9001/.well-known/agent-card.json`
  - `http://localhost:9002/.well-known/agent-card.json`
  - `http://localhost:9003/.well-known/agent-card.json`
  - `POST /a2a` on each specialist server
- Tool contract:
  - `run_specialist(user_request: str) -> str`

### Test Plan
1. Unit tests (deterministic)
- Verify each server returns a valid Agent Card with expected specialist identity.
- Verify specialist runner wiring calls intended crew `.run()` methods.
- Verify executor bridge delegates to CrewAI A2A task helpers.
- Verify Makefile includes Step 5 targets and module wiring.

2. Local integration acceptance
- `make start-agents`
- `curl http://localhost:9001/.well-known/agent-card.json`
- `curl http://localhost:9002/.well-known/agent-card.json`
- `curl http://localhost:9003/.well-known/agent-card.json`

3. Delegation smoke
- Send one JSON-RPC request to each `POST /a2a` endpoint.
- Confirm completed task state and returned agent text.

4. Regression
- Run `python -m pytest -q` for full deterministic suite.

### Assumptions
- Step 5 scope is A2A specialist servers only.
- `start-agents` does not auto-start tool servers.
- Adapter-agent architecture is intentional for `crewai==1.12.2`.

