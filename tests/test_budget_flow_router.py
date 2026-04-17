import pytest

from agents.budget.crew import BudgetOptimizerFlow, PlanContextValidation


def test_flow_returns_validation_error_when_context_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate(self: BudgetOptimizerFlow, user_request: str) -> PlanContextValidation:
        assert user_request == "optimize this"
        return PlanContextValidation(is_valid=False)

    monkeypatch.setattr(BudgetOptimizerFlow, "_validate_plan_context", fake_validate)

    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    result = flow.kickoff(inputs={"user_request": "optimize this"})

    assert "Validation error" in str(result)
    assert flow.state.iteration_count == 0


def test_flow_stops_when_budget_is_met(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate(self: BudgetOptimizerFlow, _: str) -> PlanContextValidation:
        return PlanContextValidation(
            is_valid=True,
            destination="Tokyo",
            target_budget=3000.0,
            traveler_count=2,
            trip_nights=7,
            flight_prices_per_person=[700.0],
            hotel_totals=[1800.0],
            package_summary="starting plan",
        )

    monkeypatch.setattr(BudgetOptimizerFlow, "_validate_plan_context", fake_validate)
    monkeypatch.setattr(BudgetOptimizerFlow, "_run_analysis_task", lambda self: "analysis")
    monkeypatch.setattr(
        BudgetOptimizerFlow,
        "_run_adjustment_task",
        lambda self, _: "Adjusted plan\nNew Estimated Total: $2900",
    )

    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    result = str(flow.kickoff(inputs={"user_request": "optimize this"}))

    assert "within budget" in result.lower()
    assert flow.state.current_cost == 2900.0
    assert flow.state.iteration_count == 1


def test_flow_stops_after_three_iterations_when_still_over_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate(self: BudgetOptimizerFlow, _: str) -> PlanContextValidation:
        return PlanContextValidation(
            is_valid=True,
            destination="Tokyo",
            target_budget=3000.0,
            traveler_count=2,
            trip_nights=7,
            flight_prices_per_person=[900.0],
            hotel_totals=[3000.0],
            package_summary="starting plan",
        )

    totals = [4500.0, 4100.0, 3600.0]

    def fake_adjust(self: BudgetOptimizerFlow, _: str) -> str:
        value = totals.pop(0)
        return f"Adjusted plan\nNew Estimated Total: ${value}"

    monkeypatch.setattr(BudgetOptimizerFlow, "_validate_plan_context", fake_validate)
    monkeypatch.setattr(BudgetOptimizerFlow, "_run_analysis_task", lambda self: "analysis")
    monkeypatch.setattr(BudgetOptimizerFlow, "_run_adjustment_task", fake_adjust)

    flow = BudgetOptimizerFlow(llm_model="gpt-4o", verbose=False)
    result = str(flow.kickoff(inputs={"user_request": "optimize this"}))

    assert "max iterations" in result.lower()
    assert flow.state.iteration_count == 3
    assert flow.state.current_cost == 3600.0
