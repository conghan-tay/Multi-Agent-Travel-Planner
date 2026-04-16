## Step 1 + Step 2 Stabilization and Lean Test Plan

### Summary
- Apply all four review items because they are relevant to current Step 1 and Step 2 code.
- Refactor tool-server logic into injectable plain helpers; keep `@mcp.tool()` functions as thin wrappers.
- Add a lean pytest suite for deterministic coverage of implemented Step 1 + Step 2 behavior.
- Keep `make sanity` unchanged as print-only.

### Implementation Changes
- `destination_tools`:
  - Fix month normalization bug in local events lookup (`month.strip().title()`).
  - Normalize `_LOCAL_EVENTS` month keys consistently with title case.
  - Extract `_get_destination_info(...)` and `_get_local_events(...)`; MCP tools call these helpers.
- `transport_tools`:
  - Replace hardcoded hotel `nights = 4` with date-delta computation from `checkin`/`checkout`.
  - Preserve fallback behavior for invalid/edge date inputs.
  - Extract `_search_flights(...)`, `_search_hotels(...)`, `_calculate_total_cost(...)`; MCP tools remain wrappers.
- `pricing_db_tools`:
  - Add DB-path injection seam (`_connect(db_path=...)`).
  - Extract `_lookup_avg_price(...)` and `_get_budget_tiers(...)` with optional `db_path`.
  - MCP tools stay as thin wrappers using default DB path.
- Keep existing `scripts/sanity_calls.py` and `make sanity` unchanged (print-only/manual smoke).

### Public Interface Impact
- No breaking MCP API changes (same tool names/signatures/return shape intent).
- New underscore-prefixed helper functions are introduced for testability only.
- Manual sanity script remains available and unchanged in command flow.

### Test Plan (Lean, Deterministic)
- `tests/test_destination_tools.py`
  - Known destination payload.
  - Unknown destination fallback.
  - Case-insensitive events lookup (`TOKYO`, `october`).
  - Unknown month returns empty events.
- `tests/test_transport_tools.py`
  - Flight search shape/determinism.
  - Hotel totals reflect computed nights (1-night and 7-night).
  - Invalid or non-positive date range fallback behavior.
  - Total-cost arithmetic and rounding.
- `tests/test_pricing_db_tools.py`
  - Known lookup from temp seeded DB.
  - Missing lookup returns `avg_price=0.0` + error.
  - Budget tiers present/defaulted correctly.
  - Missing DB path raises clear `FileNotFoundError`.
- `tests/test_itinerary_tools.py`
  - Step 2 tool wrappers call expected remote tool names/args (mocked client path).
  - Wrapper error handling on unreachable tool server.
- `tests/test_itinerary_cli.py`
  - `parse_args` and `--verbose`.
  - `main()` success/failure exit codes with mocked crew.
- `tests/test_itinerary_crew_config.py`
  - `_resolve_llm_model` env precedence/error.
  - Crew wiring invariants: sequential process, 3 tasks, correct context chain.

### Assumptions and Defaults
- Deterministic tests only (no live LLM/API-key E2E in this pass).
- `make sanity` remains print-only by choice; pytest suite is additional automated guardrail.
- Step 2 validation focuses on wiring/configuration/tool integration seams, not LLM text quality.
