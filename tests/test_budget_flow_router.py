import pytest

from agents.budget.crew import BudgetContextPayload, BudgetOptimizerFlow, _extract_new_total


def _valid_payload() -> BudgetContextPayload:
    return BudgetContextPayload.model_validate(
        {
            "is_valid": True,
            "reason": "",
            "origin": "NYC",
            "destination": "Tokyo",
            "target_budget": 3000.0,
            "traveler_count": 2,
            "trip_nights": 7,
            "flight_price_per_person": 900.0,
            "hotel_total": 1400.0,
            "current_total_estimate": 9999.0,
            "package_summary": "starting plan",
        }
    )


def test_flow_returns_validation_error_when_context_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate(self: BudgetOptimizerFlow, user_request: str) -> BudgetContextPayload:
        assert user_request == "optimize this"
        raise RuntimeError("Validation error: invalid budget context schema")

    monkeypatch.setattr(BudgetOptimizerFlow, "_validate_plan_context", fake_validate)

    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    result = flow.kickoff(inputs={"user_request": "optimize this"})

    assert "Validation error" in str(result)
    assert flow.state.iteration_count == 0


def test_flow_uses_deterministic_transport_baseline_not_llm_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BudgetOptimizerFlow, "_validate_plan_context", lambda self, _: _valid_payload())
    monkeypatch.setattr(BudgetOptimizerFlow, "_run_analysis_task", lambda self: "analysis")
    monkeypatch.setattr(
        BudgetOptimizerFlow,
        "_run_adjustment_task",
        lambda self, _: "Adjusted plan\nNew Estimated Total: $2900",
    )

    captured: dict[str, float] = {}

    def fake_baseline(self: BudgetOptimizerFlow, parsed: BudgetContextPayload) -> float:
        captured["flight_price_per_person"] = parsed.flight_price_per_person
        captured["hotel_total"] = parsed.hotel_total
        captured["traveler_count"] = parsed.traveler_count
        return 3584.0

    monkeypatch.setattr(BudgetOptimizerFlow, "_compute_current_total_estimate", fake_baseline)

    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    result = str(flow.kickoff(inputs={"user_request": "optimize this"}))

    assert "within budget" in result.lower()
    assert captured == {
        "flight_price_per_person": 900.0,
        "hotel_total": 1400.0,
        "traveler_count": 2,
    }
    assert flow.state.current_cost == 2900.0


def test_flow_stops_after_three_iterations_when_still_over_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BudgetOptimizerFlow, "_validate_plan_context", lambda self, _: _valid_payload())
    monkeypatch.setattr(BudgetOptimizerFlow, "_compute_current_total_estimate", lambda self, _: 5000.0)
    monkeypatch.setattr(BudgetOptimizerFlow, "_run_analysis_task", lambda self: "analysis")

    totals = [4500.0, 4100.0, 3600.0]

    def fake_adjust(self: BudgetOptimizerFlow, _: str) -> str:
        value = totals.pop(0)
        return f"Adjusted plan\nNew Estimated Total: ${value}"

    monkeypatch.setattr(BudgetOptimizerFlow, "_run_adjustment_task", fake_adjust)

    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    result = str(flow.kickoff(inputs={"user_request": "optimize this"}))

    assert "max iterations" in result.lower()
    assert flow.state.iteration_count == 3
    assert flow.state.current_cost == 3600.0


def test_extract_new_total_accepts_plain_and_markdown_bold() -> None:
    assert _extract_new_total("New Estimated Total: $3000") == 3000.0
    assert _extract_new_total("**New Estimated Total**: $3000") == 3000.0


def test_extract_new_total_returns_none_when_missing_numeric_value() -> None:
    assert _extract_new_total("New Estimated Total: TBD") is None
