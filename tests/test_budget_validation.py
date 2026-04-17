from agents.budget.crew import BudgetOptimizerFlow


def test_normalize_validation_payload_requires_budget_and_context() -> None:
    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    payload = {
        "is_valid": True,
        "destination": "Tokyo",
        "target_budget": 3000,
        "traveler_count": 2,
        "trip_nights": 7,
        "flight_prices_per_person": [],
        "hotel_totals": [],
        "current_total_estimate": None,
        "package_summary": "plan",
    }

    parsed = flow._normalize_validation_payload(payload, "request")
    assert parsed.is_valid is False


def test_normalize_validation_payload_accepts_minimum_explicit_fields() -> None:
    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    payload = {
        "is_valid": True,
        "destination": "Tokyo",
        "target_budget": 3000,
        "traveler_count": 2,
        "trip_nights": 7,
        "flight_prices_per_person": [800],
        "hotel_totals": [1200],
        "current_total_estimate": None,
        "package_summary": "plan",
    }

    parsed = flow._normalize_validation_payload(payload, "request")
    assert parsed.is_valid is True


def test_normalize_validation_payload_accepts_pasted_summary_with_total() -> None:
    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    payload = {
        "is_valid": True,
        "destination": "Tokyo",
        "target_budget": 3000,
        "traveler_count": None,
        "trip_nights": None,
        "flight_prices_per_person": [],
        "hotel_totals": [],
        "current_total_estimate": 4200,
        "package_summary": "Pasted package summary with cost details",
    }

    parsed = flow._normalize_validation_payload(payload, "request")
    assert parsed.is_valid is True
    assert parsed.current_total_estimate == 4200
