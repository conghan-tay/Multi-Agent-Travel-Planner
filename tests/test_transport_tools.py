from tool_servers.transport_tools.main import (
    _calculate_total_cost,
    _search_flights,
    _search_hotels,
)


def test_search_flights_returns_deterministic_shape() -> None:
    first = _search_flights("NYC", "Tokyo", "2026-10-01")
    second = _search_flights("NYC", "Tokyo", "2026-10-01")
    assert first == second
    assert len(first["flights"]) == 3
    assert {"airline", "flight_number", "departure", "arrival", "duration", "price_per_person"} <= set(
        first["flights"][0]
    )


def test_search_hotels_total_uses_computed_nights() -> None:
    one_night = _search_hotels("Tokyo", "2026-10-01", "2026-10-02")
    seven_nights = _search_hotels("Tokyo", "2026-10-01", "2026-10-08")

    for hotel in one_night["hotels"]:
        assert hotel["total_price"] == hotel["price_per_night"] * 1

    for hotel in seven_nights["hotels"]:
        assert hotel["total_price"] == hotel["price_per_night"] * 7


def test_search_hotels_fallback_behavior_for_invalid_or_non_positive_dates() -> None:
    invalid_dates = _search_hotels("Tokyo", "not-a-date", "still-not-a-date")
    same_day = _search_hotels("Tokyo", "2026-10-05", "2026-10-05")
    reversed_range = _search_hotels("Tokyo", "2026-10-08", "2026-10-01")

    for hotel in invalid_dates["hotels"]:
        assert hotel["total_price"] == hotel["price_per_night"] * 4

    for hotel in same_day["hotels"]:
        assert hotel["total_price"] == hotel["price_per_night"] * 1

    for hotel in reversed_range["hotels"]:
        assert hotel["total_price"] == hotel["price_per_night"] * 1


def test_calculate_total_cost_rounding_and_breakdown() -> None:
    result = _calculate_total_cost(flight_price=333.333, hotel_total=555.555, num_travelers=3)
    assert result["flights_total"] == 1000.0
    assert result["hotels_total"] == 555.55
    assert result["taxes_and_fees"] == 186.67
    assert result["grand_total"] == 1742.22
