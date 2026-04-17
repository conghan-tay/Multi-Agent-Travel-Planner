## Step 4 Hardening Plan: Strict Schema + Deterministic Costing + Pricing Type Fix

### Summary
Refactor budget-input validation to strict Pydantic enforcement, switch `current_total_estimate` to deterministic calculation via transport `calculate_total_cost`, simplify input contract to one flight price + one hotel total, and require both origin and destination.  
Also fix pricing lookup misses by removing ambiguous travel-type strings from agent tool calls.

### Key Changes
- **Strict validator schema (fail fast)**
  - Replace free-form JSON normalization with a dedicated Pydantic model for `validate_budget_context_task` output.
  - Required fields: `origin`, `destination`, `target_budget`, `traveler_count`, `trip_nights` (or valid date range), `flight_price_per_person`, `hotel_total`.
  - Reject if schema invalid, missing required fields, non-positive numeric values, or inconsistent date/trip-length values.
  - No heuristic fallback for invalid schema (per your strict mode choice).

- **Deterministic `current_total_estimate`**
  - Stop trusting LLM-provided `current_total_estimate` as source of truth.
  - Compute it in code using `transport-tools.calculate_total_cost(flight_price, hotel_total, num_travelers)`.
  - Use returned `grand_total` as canonical baseline for flow state.
  - Update validator prompt to request fields only; allow `current_total_estimate` as optional echo/debug field, not authoritative.

- **Simplified prompt/input contract**
  - Standardize Step 4 input to single-price package context:
    - one flight price per traveler,
    - one hotel total for entire stay (shared),
    - origin + destination,
    - dates/trip length,
    - traveler count,
    - target budget.
  - Update CLI docs/examples to this canonical format.

- **Fix pricing lookup misses (`accommodations`/`flights` errors)**
  - Remove open-ended travel-type usage in budget analysis/adjustment tasks.
  - Introduce deterministic budget helper tools with constrained semantics:
    - `lookup_avg_flight_price(destination)` -> maps to `travel_type="flight"`
    - `lookup_avg_hotel_price(destination, tier)` -> maps to valid `hotel_budget|hotel_midrange|hotel_luxury`
  - Update budget agents/tasks to use these wrappers only.
  - Keep raw `lookup_avg_price` wrapper internal (or for tests), but not directly exposed to LLM-facing budget agents.

- **Flow output robustness (from your `output.txt`)**
  - Harden `New Estimated Total` extraction to tolerate markdown formatting variants (e.g., `**New Estimated Total**: $3000`) while still requiring numeric total presence.
  - Keep hard failure when no parseable final total exists.

### Public Interface / Contract Updates
- `python -m agents.budget "<request>"` contract now explicitly requires:
  - `origin`, `destination`, `target budget`, `traveler count`, `dates/trip length`, `flight price per traveler`, `hotel total`.
- Validation errors become explicit schema/field errors (not heuristic “missing context” only).
- Budget flow baseline cost is now deterministic and transport-tool-derived (`grand_total`), not LLM-inferred.

### Test Plan
- **Schema validation tests**
  - Valid payload with all required fields passes.
  - Missing `origin` or `destination` fails.
  - Multiple/array prices in validator output fail under strict single-price schema.
  - Invalid numeric/date values fail with clear error.
- **Cost calculation tests**
  - For `flight_price=900`, `hotel_total=1400`, `travelers=2`, assert baseline uses transport tool `grand_total` (includes 12% taxes/fees).
  - Assert LLM `current_total_estimate` mismatch does not override deterministic value.
- **Pricing lookup normalization tests**
  - Budget agents no longer send `accommodation(s)`/`flights` to pricing DB.
  - Wrapper tools call valid travel types only and return non-error rows for seeded destinations.
- **Flow parser tests**
  - Accept `New Estimated Total: $3000` and `**New Estimated Total**: $3000`.
  - Fail if no numeric final total is present.

### Assumptions
- `transport-tools` remains available during budget runs for deterministic baseline cost calculation.
- Destination pricing remains seeded via existing `data/seed_db.py`; no DB schema change is needed.
- Step 4 remains direct specialist mode (no A2A/orchestrator changes in this pass).
