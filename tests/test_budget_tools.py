import pytest

from agents.budget import tools as budget_tools


def test_lookup_avg_price_wrapper_delegates_with_expected_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"avg_price": 1200.0}

    monkeypatch.setattr(budget_tools, "_run_tool_call", fake_run_tool_call)
    result = budget_tools.lookup_avg_price_tool.func("Tokyo", "flight")

    assert result["avg_price"] == 1200.0
    assert captured == {
        "name": "lookup_avg_price",
        "arguments": {"destination": "Tokyo", "travel_type": "flight"},
    }


def test_get_budget_tiers_wrapper_delegates_with_expected_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"budget": {"hotel_per_night": 95.0, "daily_spend": 80.0}}

    monkeypatch.setattr(budget_tools, "_run_tool_call", fake_run_tool_call)
    result = budget_tools.get_budget_tiers_tool.func("Tokyo")

    assert result["budget"]["hotel_per_night"] == 95.0
    assert captured == {
        "name": "get_budget_tiers",
        "arguments": {"destination": "Tokyo"},
    }


def test_run_tool_call_wraps_connectivity_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_pricing_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise ConnectionError(f"Cannot call {name} with {arguments}")

    monkeypatch.setattr(budget_tools, "_call_pricing_tool", fake_call_pricing_tool)
    with pytest.raises(RuntimeError, match="Unable to reach pricing-db-tools"):
        budget_tools._run_tool_call("lookup_avg_price", {"destination": "Tokyo", "travel_type": "flight"})
