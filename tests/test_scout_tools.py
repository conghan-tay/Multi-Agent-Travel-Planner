import pytest

from agents.scout import tools as scout_tools


def test_search_flights_wrapper_delegates_with_expected_args(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"flights": []}

    monkeypatch.setattr(scout_tools, "_run_tool_call", fake_run_tool_call)
    result = scout_tools.search_flights_tool.func("NYC", "Tokyo", "2026-10-01")

    assert result["flights"] == []
    assert captured == {
        "name": "search_flights",
        "arguments": {"origin": "NYC", "destination": "Tokyo", "date": "2026-10-01"},
    }


def test_search_hotels_wrapper_delegates_with_expected_args(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"hotels": []}

    monkeypatch.setattr(scout_tools, "_run_tool_call", fake_run_tool_call)
    result = scout_tools.search_hotels_tool.func("Tokyo", "2026-10-01", "2026-10-08")

    assert result["hotels"] == []
    assert captured == {
        "name": "search_hotels",
        "arguments": {
            "destination": "Tokyo",
            "checkin": "2026-10-01",
            "checkout": "2026-10-08",
        },
    }


def test_calculate_total_cost_wrapper_delegates_with_expected_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"grand_total": 1234.56}

    monkeypatch.setattr(scout_tools, "_run_tool_call", fake_run_tool_call)
    result = scout_tools.calculate_total_cost_tool.func(500.0, 400.0, 2)

    assert result["grand_total"] == 1234.56
    assert captured == {
        "name": "calculate_total_cost",
        "arguments": {"flight_price": 500.0, "hotel_total": 400.0, "num_travelers": 2},
    }


def test_run_tool_call_wraps_connectivity_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_transport_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise ConnectionError(f"Cannot call {name} with {arguments}")

    monkeypatch.setattr(scout_tools, "_call_transport_tool", fake_call_transport_tool)
    with pytest.raises(RuntimeError, match="Unable to reach transport-tools"):
        scout_tools._run_tool_call("search_flights", {"origin": "NYC", "destination": "Tokyo", "date": "2026-10-01"})
