import pytest
from pydantic import ValidationError

from agents.budget.crew import BudgetContextPayload, BudgetOptimizerFlow


def test_budget_context_payload_valid_with_trip_nights() -> None:
    payload = BudgetContextPayload.model_validate(
        {
            "is_valid": True,
            "reason": "",
            "origin": "NYC",
            "destination": "Tokyo",
            "target_budget": 3000,
            "traveler_count": 2,
            "trip_nights": 7,
            "flight_price_per_person": 900,
            "hotel_total": 1400,
            "current_total_estimate": 9999,
        }
    )

    assert payload.origin == "NYC"
    assert payload.destination == "Tokyo"
    assert payload.trip_nights == 7


def test_budget_context_payload_derives_trip_nights_from_dates() -> None:
    payload = BudgetContextPayload.model_validate(
        {
            "is_valid": True,
            "reason": "",
            "origin": "NYC",
            "destination": "Tokyo",
            "target_budget": 3000,
            "traveler_count": 2,
            "start_date": "2026-10-01",
            "end_date": "2026-10-08",
            "flight_price_per_person": 900,
            "hotel_total": 1400,
        }
    )

    assert payload.trip_nights == 7


def test_budget_context_payload_requires_origin_and_destination() -> None:
    with pytest.raises(ValidationError):
        BudgetContextPayload.model_validate(
            {
                "is_valid": True,
                "reason": "",
                "destination": "Tokyo",
                "target_budget": 3000,
                "traveler_count": 2,
                "trip_nights": 7,
                "flight_price_per_person": 900,
                "hotel_total": 1400,
            }
        )


def test_budget_context_payload_rejects_array_for_single_price_fields() -> None:
    with pytest.raises(ValidationError):
        BudgetContextPayload.model_validate(
            {
                "is_valid": True,
                "reason": "",
                "origin": "NYC",
                "destination": "Tokyo",
                "target_budget": 3000,
                "traveler_count": 2,
                "trip_nights": 7,
                "flight_price_per_person": [900, 1050],
                "hotel_total": 1400,
            }
        )


def test_budget_context_payload_rejects_inconsistent_nights_and_dates() -> None:
    with pytest.raises(ValidationError, match="trip_nights is inconsistent"):
        BudgetContextPayload.model_validate(
            {
                "is_valid": True,
                "reason": "",
                "origin": "NYC",
                "destination": "Tokyo",
                "target_budget": 3000,
                "traveler_count": 2,
                "trip_nights": 5,
                "start_date": "2026-10-01",
                "end_date": "2026-10-08",
                "flight_price_per_person": 900,
                "hotel_total": 1400,
            }
        )


def test_budget_context_payload_rejects_is_valid_false() -> None:
    with pytest.raises(ValidationError, match="missing destination"):
        BudgetContextPayload.model_validate(
            {
                "is_valid": False,
                "reason": "missing destination",
                "origin": "NYC",
                "destination": "Tokyo",
                "target_budget": 3000,
                "traveler_count": 2,
                "trip_nights": 7,
                "flight_price_per_person": 900,
                "hotel_total": 1400,
            }
        )


def test_validate_plan_context_returns_typed_output_from_task(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    expected = BudgetContextPayload.model_validate(
        {
            "is_valid": True,
            "reason": "",
            "origin": "NYC",
            "destination": "Tokyo",
            "target_budget": 3000,
            "traveler_count": 2,
            "trip_nights": 7,
            "flight_price_per_person": 900,
            "hotel_total": 1400,
        }
    )

    class DummyTaskOutput:
        def __init__(self, pydantic):
            self.pydantic = pydantic

    class DummyResult:
        tasks_output = [DummyTaskOutput(expected)]

    class DummyCrew:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def kickoff(self, inputs):
            assert "user_request" in inputs
            return DummyResult()

    monkeypatch.setattr("agents.budget.crew.Crew", DummyCrew)
    parsed = flow._validate_plan_context("request")
    assert isinstance(parsed, BudgetContextPayload)
    assert parsed.destination == "Tokyo"


def test_validate_plan_context_fails_when_typed_output_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)

    class DummyTaskOutput:
        pydantic = None

    class DummyResult:
        tasks_output = [DummyTaskOutput()]

    class DummyCrew:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def kickoff(self, inputs):
            return DummyResult()

    monkeypatch.setattr("agents.budget.crew.Crew", DummyCrew)
    with pytest.raises(RuntimeError, match="typed output missing"):
        flow._validate_plan_context("request")


def test_validate_plan_context_fails_when_typed_output_wrong_type(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)

    class DummyTaskOutput:
        pydantic = {"origin": "NYC"}

    class DummyResult:
        tasks_output = [DummyTaskOutput()]

    class DummyCrew:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def kickoff(self, inputs):
            return DummyResult()

    monkeypatch.setattr("agents.budget.crew.Crew", DummyCrew)
    with pytest.raises(RuntimeError, match="invalid type"):
        flow._validate_plan_context("request")
