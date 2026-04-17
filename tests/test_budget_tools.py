import pytest

from agents.budget import tools as budget_tools


def test_lookup_avg_flight_price_wrapper_maps_to_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_pricing(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"avg_price": 850.0}

    monkeypatch.setattr(budget_tools, "_run_pricing_tool_call", fake_run_pricing)
    result = budget_tools.lookup_avg_flight_price_tool.func("Tokyo")

    assert result["avg_price"] == 850.0
    assert captured == {
        "name": "lookup_avg_price",
        "arguments": {"destination": "Tokyo", "travel_type": "flight"},
    }


def test_lookup_avg_hotel_price_wrapper_maps_tier_to_valid_travel_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_pricing(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"avg_price": 180.0}

    monkeypatch.setattr(budget_tools, "_run_pricing_tool_call", fake_run_pricing)
    result = budget_tools.lookup_avg_hotel_price_tool.func("Tokyo", "midrange")

    assert result["avg_price"] == 180.0
    assert captured == {
        "name": "lookup_avg_price",
        "arguments": {"destination": "Tokyo", "travel_type": "hotel_midrange"},
    }


def test_lookup_avg_hotel_price_rejects_invalid_tier() -> None:
    with pytest.raises(ValueError, match="tier must be one of"):
        budget_tools.lookup_avg_hotel_price_tool.func("Tokyo", "accommodations")


def test_calculate_total_cost_transport_delegates_with_expected_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_transport(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"grand_total": 3584.0}

    monkeypatch.setattr(budget_tools, "_run_transport_tool_call", fake_run_transport)
    result = budget_tools.calculate_total_cost_transport(900.0, 1400.0, 2)

    assert result["grand_total"] == 3584.0
    assert captured == {
        "name": "calculate_total_cost",
        "arguments": {"flight_price": 900.0, "hotel_total": 1400.0, "num_travelers": 2},
    }


def test_run_pricing_tool_call_wraps_connectivity_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise ConnectionError(f"Cannot call {name} with {arguments}")

    monkeypatch.setattr(budget_tools, "_call_pricing_tool", fake_call)
    with pytest.raises(RuntimeError, match="Unable to reach pricing-db-tools"):
        budget_tools._run_pricing_tool_call(
            "lookup_avg_price", {"destination": "Tokyo", "travel_type": "flight"}
        )


def test_run_transport_tool_call_wraps_connectivity_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise ConnectionError(f"Cannot call {name} with {arguments}")

    monkeypatch.setattr(budget_tools, "_call_transport_tool", fake_call)
    with pytest.raises(RuntimeError, match="Unable to reach transport-tools"):
        budget_tools._run_transport_tool_call(
            "calculate_total_cost",
            {"flight_price": 900.0, "hotel_total": 1400.0, "num_travelers": 2},
        )
