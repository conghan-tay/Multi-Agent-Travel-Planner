## Step 1 Plan: Decoupled Tool Servers (Lean, Incremental)

### Summary
Implement Module 1 as a minimal vertical slice: three independent FastMCP tool servers, a seeded SQLite database, Make targets to run/stop services, and smoke checks via `curl` + direct tool-call sanity.  
Primary goal: pass PRD Step 1 verification before any agent/orchestrator work.

### Implementation Changes (Incremental Slices)
1. **Project scaffold + dependencies**
- Add Python package layout for `tool_servers` and `data` seed utilities.
- Add `requirements.txt` pinned to `crewai[a2a]`, `fastmcp`, `uvicorn`, `python-dotenv`, `a2a-sdk`.
- Add `.env.example` with only Step-1-relevant vars (ports, optional defaults).

2. **`destination-tools` server (`:8001`)**
- Implement tools:
  - `get_destination_info(destination: str)`
  - `get_local_events(destination: str, month: str)`
- Return deterministic mock JSON per architecture contract (stable fields, predictable values).
- Expose `/tools` and MCP-compatible tool invocation endpoint via FastMCP runtime.

3. **`transport-tools` server (`:8002`)**
- Implement tools:
  - `search_flights(origin: str, destination: str, date: str)`
  - `search_hotels(destination: str, checkin: str, checkout: str)`
  - `calculate_total_cost(flight_price: float, hotel_total: float, num_travelers: int)`  
- Keep pricing logic deterministic and transparent (fixed tax/fee rule).

4. **`pricing-db-tools` server (`:8003`) + DB seed**
- Add SQLite schema:
  - `destinations` (avg price by destination + travel_type)
  - `budget_tiers` (budget/midrange/luxury bands)
- Add idempotent seed command (`make seed-db`) that creates/populates `data/travel.db`.
- Implement tools:
  - `lookup_avg_price(destination: str, travel_type: str)`
  - `get_budget_tiers(destination: str)`

5. **Operations + smoke verification**
- Add `Makefile` targets: `seed-db`, `start-tools`, `stop`, and optional `check-ports`.
- `start-tools` runs all 3 servers in background with clear logs/PIDs for easy debugging.
- Add short “Step 1 verification” section in README with exact commands and expected outputs.

### Public Interfaces Locked in Step 1
- **Ports**: `8001`, `8002`, `8003`.
- **Tool contracts**:
  - Destination tools: `get_destination_info`, `get_local_events`.
  - Transport tools: `search_flights`, `search_hotels`, `calculate_total_cost(flight_price, hotel_total, num_travelers)`.
  - Pricing DB tools: `lookup_avg_price`, `get_budget_tiers`.
- **Verification endpoint**: `GET /tools` must list tools on each server.

### Test Plan (Step-1 Acceptance)
1. Run `make seed-db`; verify `data/travel.db` exists and tables contain seed rows.
2. Run `make start-tools`; verify ports `8001/8002/8003` are bound.
3. Run:
   - `curl http://localhost:8001/tools`
   - `curl http://localhost:8002/tools`
   - `curl http://localhost:8003/tools`
   Confirm expected tool names appear per server.
4. Execute one tool-call sanity check per server (direct MCP call or minimal local caller) and confirm JSON shape matches contract.
5. Restart one server independently and confirm others remain unaffected (decoupling check).

### Assumptions / Defaults
- `calculate_total_cost` uses the **scalar-argument signature** from the architecture doc.
- Step 1 remains a **minimal vertical slice**: no agents, no A2A servers, no cooldown/session logic, no Docker.
- Mock data is deterministic to make debugging and diff review straightforward.
