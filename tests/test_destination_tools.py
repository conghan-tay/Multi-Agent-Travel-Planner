from tool_servers.destination_tools.main import _get_destination_info, _get_local_events


def test_known_destination_payload() -> None:
    result = _get_destination_info("Tokyo")
    assert result["destination"] == "Tokyo"
    assert len(result["attractions"]) == 5


def test_unknown_destination_fallback() -> None:
    result = _get_destination_info("Narnia")
    assert result["destination"] == "Narnia"
    assert len(result["attractions"]) == 3


def test_local_events_case_insensitive_month_and_destination() -> None:
    result = _get_local_events("TOKYO", "october")
    assert result["destination"] == "Tokyo"
    assert result["month"] == "October"
    assert len(result["events"]) == 2


def test_local_events_unknown_month_returns_empty() -> None:
    result = _get_local_events("Tokyo", "February")
    assert result["events"] == []
