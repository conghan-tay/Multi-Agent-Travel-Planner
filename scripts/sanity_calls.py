"""Step-1 function-level sanity checks for all tool contracts."""

from __future__ import annotations

from data.seed_db import seed_database
from tool_servers.destination_tools.main import get_destination_info, get_local_events
from tool_servers.pricing_db_tools.main import get_budget_tiers, lookup_avg_price
from tool_servers.transport_tools.main import (
    calculate_total_cost,
    search_flights,
    search_hotels,
)


if __name__ == "__main__":
    seed_database()

    print("[destination-tools]", get_destination_info.fn("Tokyo")["destination"])
    print(
        "[destination-tools]",
        len(get_local_events.fn("Tokyo", "October")["events"]),
    )

    flights = search_flights.fn("NYC", "Tokyo", "2026-10-01")["flights"]
    hotels = search_hotels.fn("Tokyo", "2026-10-01", "2026-10-05")["hotels"]
    print("[transport-tools]", len(flights), len(hotels))
    print(
        "[transport-tools]",
        calculate_total_cost.fn(
            flight_price=flights[0]["price_per_person"],
            hotel_total=hotels[0]["total_price"],
            num_travelers=2,
        )["grand_total"],
    )

    print(
        "[pricing-db-tools]",
        lookup_avg_price.fn("Tokyo", "hotel_midrange")["avg_price"],
    )
    print(
        "[pricing-db-tools]",
        get_budget_tiers.fn("Tokyo")["budget"]["hotel_per_night"],
    )
