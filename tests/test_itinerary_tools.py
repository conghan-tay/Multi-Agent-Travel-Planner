import pytest

from agents.itinerary import tools as itinerary_tools


def test_destination_tool_wrapper_delegates_with_expected_args(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"destination": "Tokyo"}

    monkeypatch.setattr(itinerary_tools, "_run_tool_call", fake_run_tool_call)
    result = itinerary_tools.get_destination_info_tool.func("Tokyo")

    assert result["destination"] == "Tokyo"
    assert captured == {"name": "get_destination_info", "arguments": {"destination": "Tokyo"}}


def test_local_events_tool_wrapper_delegates_with_expected_args(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {"events": []}

    monkeypatch.setattr(itinerary_tools, "_run_tool_call", fake_run_tool_call)
    result = itinerary_tools.get_local_events_tool.func("Tokyo", "October")

    assert result["events"] == []
    assert captured == {
        "name": "get_local_events",
        "arguments": {"destination": "Tokyo", "month": "October"},
    }


def test_run_tool_call_wraps_connectivity_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_destination_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise ConnectionError(f"Cannot call {name} with {arguments}")

    monkeypatch.setattr(itinerary_tools, "_call_destination_tool", fake_call_destination_tool)
    with pytest.raises(RuntimeError, match="Unable to reach destination-tools"):
        itinerary_tools._run_tool_call("get_destination_info", {"destination": "Tokyo"})
