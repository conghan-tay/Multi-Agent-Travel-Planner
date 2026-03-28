# CrewAI Multi-Agent System — Travel Planning

> A locally-running multi-agent system built with CrewAI that replicates the architectural concepts from Google's [Agentverse Architect](https://codelabs.developers.google.com/agentverse-architect/instructions) codelab — without any reliance on Google Cloud, Google ADK, or managed cloud services.

---

## What this is

This project is a **self-directed learning exercise** in multi-agent system architecture. It demonstrates five progressive architectural concepts using the travel planning domain as its real-world context:

| Module | Concept | Implementation |
|--------|---------|----------------|
| 1 | Decoupled tool servers | 3× FastMCP servers (destination info, transport search, pricing DB) |
| 2 | Workflow agents | Sequential itinerary builder, Parallel flight+hotel scout, Loop budget optimizer |
| 3 | A2A orchestration | TravelOrchestratorCrew delegates to specialists via Agent-to-Agent protocol |
| 4 | Interceptor pattern | CooldownGuard enforces 60-second cooldown per specialist |
| 5 | Agent state & memory | Session state tracks last-used specialist; prompt injection drives adaptive routing |

It is **not** a production travel app. Tool servers return deterministic mock data. There is no UI. Everything runs from the CLI.

---

## Architecture overview

```
CLI (main.py)
    │
    └── TravelOrchestratorAgent  [A2A Client]
            │
            ├──[A2A :9001]── ItineraryBuilderCrew    (Sequential)
            │                   ├── DestinationResearchAgent  → destination-tools :8001
            │                   ├── ItineraryDraftAgent
            │                   └── ItineraryFormatterAgent
            │
            ├──[A2A :9002]── FlightHotelScoutCrew    (Parallel → Sequential)
            │                   ├── FlightSearchAgent  [async] → transport-tools :8002
            │                   ├── HotelSearchAgent   [async] → transport-tools :8002
            │                   └── ResultMergerAgent           → transport-tools :8002
            │
            └──[A2A :9003]── BudgetOptimizerCrew     (Loop / Flow)
                                ├── BudgetAnalysisAgent  → pricing-db-tools :8003
                                └── PlanAdjustmentAgent  → pricing-db-tools :8003
```

**Port map:**

| Port | Service | Role |
|------|---------|------|
| 8001 | destination-tools | MCP — destination info & events |
| 8002 | transport-tools | MCP — flights, hotels, cost calc |
| 8003 | pricing-db-tools | MCP — SQLite pricing lookups |
| 9001 | itinerary-a2a | A2A server for ItineraryBuilderCrew |
| 9002 | scout-a2a | A2A server for FlightHotelScoutCrew |
| 9003 | budget-a2a | A2A server for BudgetOptimizerCrew |

---

## Prerequisites

- **Python 3.11+**
- An **OpenAI API key** (`sk-...`) **or** an **Anthropic API key** (`sk-ant-...`) — not both required
- `pip` or [`uv`](https://docs.astral.sh/uv/) for dependency management

---

## Installation

```bash
git clone <your-repo-url>
cd crewai-mas

# With pip
pip install -r requirements.txt

# Or with uv (faster)
uv pip install -r requirements.txt
```

`requirements.txt` includes: `crewai[a2a]`, `fastmcp`, `uvicorn`, `python-dotenv`, `a2a-sdk`

---

## Configuration

Copy `.env.example` to `.env` and set your LLM provider:

```bash
cp .env.example .env
```

**.env options:**

```env
# ── LLM Provider — set ONE of these ──────────────────────────────────────
LLM_PROVIDER=openai           # or: anthropic

# OpenAI (if LLM_PROVIDER=openai)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o           # default

# Anthropic (if LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6   # default

# ── Cooldown ──────────────────────────────────────────────────────────────
COOLDOWN_SECONDS=60           # reduce to 10 for faster module testing
```

Switching between OpenAI and Anthropic requires only changing `LLM_PROVIDER` — no code changes.

---

## Running the system

Start all services, then launch the CLI. Each command runs in a separate terminal.

### Step 1 — Seed the database (first run only)

```bash
make seed-db
```

Creates `data/travel.db` and populates destination pricing reference data.

### Step 2 — Start tool servers

```bash
make start-tools
```

Starts all three MCP tool servers (ports 8001, 8002, 8003) as background processes.

### Step 3 — Start A2A specialist servers

```bash
make start-agents
```

Starts all three A2A specialist servers (ports 9001, 9002, 9003) as background processes.

### Step 4 — Run the CLI

```bash
python main.py
```

Opens an interactive REPL. Enter a travel request and press Enter.

### Stopping all services

```bash
make stop
```

---

## Basic usage

Once `python main.py` is running, enter natural-language travel requests:

```
> Plan a 5-day trip to Tokyo in October for 2 people.
> Find flights and hotels from New York to Tokyo, Oct 1–8.
> Our total budget is $3000. Optimize the plan.
```

The orchestrator routes each request to the appropriate specialist automatically. Use `verbose=True` in the orchestrator config to see the full LLM reasoning and tool call trace.

```
> exit
```

Ends the session.

---

## Repository structure

```
crewai-mas/
├── tool_servers/
│   ├── destination_tools/
│   │   └── main.py            # FastMCP server — get_destination_info, get_local_events
│   ├── transport_tools/
│   │   └── main.py            # FastMCP server — search_flights, search_hotels, calculate_total_cost
│   └── pricing_db_tools/
│       └── main.py            # FastMCP server — lookup_avg_price, get_budget_tiers
│
├── agents/
│   ├── itinerary/
│   │   └── crew.py            # ItineraryBuilderCrew (Sequential) — 3 agents, 3 tasks
│   ├── scout/
│   │   └── crew.py            # FlightHotelScoutCrew (Parallel) — 3 agents, 3 tasks
│   ├── budget/
│   │   └── crew.py            # BudgetOptimizerCrew (Loop/Flow) — 2 agents, 2 tasks
│   └── orchestrator/
│       └── crew.py            # TravelOrchestratorCrew — A2AClientConfig × 3
│
├── a2a_servers/
│   ├── itinerary_server.py    # Exposes ItineraryBuilderCrew on port 9001
│   ├── scout_server.py        # Exposes FlightHotelScoutCrew on port 9002
│   └── budget_server.py       # Exposes BudgetOptimizerCrew on port 9003
│
├── guards/
│   └── cooldown_guard.py      # CooldownGuard class — applied to all specialists
│
├── state/
│   └── session.py             # In-memory session dict + prompt injector
│
├── shared/
│   └── models.py              # Shared TypedDicts — state schemas, return types
│
├── data/
│   └── travel.db              # SQLite — auto-created by make seed-db
│
├── main.py                    # CLI entry point — REPL loop
├── .env.example               # LLM config template
├── Makefile                   # All start/stop/test commands
├── requirements.txt
└── README.md
```

---

## Module-by-module verification

Each module can be tested independently before wiring everything together.

### Module 1 — Tool servers

```bash
# One-command setup (creates .venv with Python 3.13.12, installs deps, seeds DB)
make bootstrap

# Start all tool servers
make start-tools

# Confirm tool listings are live
curl http://localhost:8001/tools
curl http://localhost:8002/tools
curl http://localhost:8003/tools

# Function-level tool contract sanity checks
make sanity

# Endpoint-level verification checks
make verify-tools

# Stop all tool servers
make stop
```

Expected: JSON list of available tools for each server.

Note: `requirements.txt` is intentionally Step-1-only. For later modules
(CrewAI/A2A), install `requirements.agents.txt`.

### Module 2 — Specialist crews (direct, bypassing A2A)

```bash
python -m agents.itinerary "Plan a trip to Paris"
python -m agents.scout "Flights and hotels NYC to Paris, June 1-7"
python -m agents.budget "Optimize Paris trip for $2000 budget"
```

### Module 3 — A2A Agent Cards

```bash
curl http://localhost:9001/.well-known/agent-card.json | python3 -m json.tool
curl http://localhost:9002/.well-known/agent-card.json | python3 -m json.tool
curl http://localhost:9003/.well-known/agent-card.json | python3 -m json.tool
```

Expected: valid JSON Agent Cards with `name`, `description`, and `skills` fields.

### Module 4 — Cooldown guard

Set `COOLDOWN_SECONDS=10` in `.env` for faster testing. Start `python main.py` and enter the same itinerary request twice within 10 seconds. The second call should be blocked:

```
> Plan a trip to Tokyo
[... itinerary output ...]
> Plan a trip to Kyoto
[Cooldown active for itinerary_specialist. Try again in 8 seconds.]
```

### Module 5 — Session state

Run three consecutive requests and observe that the orchestrator avoids repeating the same specialist:

```
> Plan a trip to Tokyo          # → routes to itinerary_specialist
> Find flights to Tokyo         # → routes to scout_specialist (not itinerary)
> Optimize for $2500 budget     # → routes to budget_specialist
```

---

## Key design decisions

**Why FastMCP instead of embedding tools directly in agents?**
Embedding tools in agents couples the tool implementation to the agent, making it impossible to reuse the same tool across multiple crews. FastMCP servers are standalone processes — any agent in any crew can call them without importing their code.

**Why CrewAI Flows for the loop agent?**
CrewAI's `@router` decorator provides an explicit, inspectable exit condition — equivalent to ADK's `LoopAgent` `max_iterations` and state check. A recursive `crew.kickoff()` approach would work but is harder to reason about and instrument.

**Why SQLite instead of PostgreSQL?**
The Google ADK tutorial uses Cloud SQL. SQLite gives the same SQL interface and the same structured-data-lookup learning without requiring a running database server. The tool interface is identical — swapping to PostgreSQL later requires only changing the connection string.

**Why in-memory session state?**
The learning objective is the callback pattern and prompt injection, not state persistence. Adding a database here provides no architectural insight for a single-user local session.

**Switching LLMs**
Set `LLM_PROVIDER=anthropic` in `.env` and add your `ANTHROPIC_API_KEY`. CrewAI's LLM abstraction handles the provider switch — no agent or crew code changes required.

---

## Companion documents

| Document | Contents |
|----------|----------|
| `PRD.docx` | Product requirements, learning objectives, full module scope |
| `ARCHITECTURE.docx` | Agent definitions (role/goal/backstory), task definitions, tool schemas, event sequence diagrams, data contracts |

---

## Acknowledgements

Architecture based on the [Google ADK Agentverse Architect codelab](https://codelabs.developers.google.com/agentverse-architect/instructions). Rebuilt using [CrewAI](https://docs.crewai.com) and [FastMCP](https://github.com/jlowin/fastmcp) for local, cloud-free operation.
