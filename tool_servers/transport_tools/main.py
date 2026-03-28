"""FastMCP server: transport-tools (port 8002)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("transport-tools")


def _date_label(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
    except ValueError:
        return date_str


def _search_flights(origin: str, destination: str, date: str) -> dict[str, list[dict[str, Any]]]:
    """Return deterministic mock flight options."""
    price_seed = (len(origin.strip()) * 13) + (len(destination.strip()) * 17)
    base_price = 260 + (price_seed % 200)
    label = _date_label(date)

    flights = [
        {
            "airline": "SkyBridge Air",
            "flight_number": "SB102",
            "departure": f"{label} 08:15",
            "arrival": f"{label} 16:40",
            "duration": "8h 25m",
            "price_per_person": float(base_price),
        },
        {
            "airline": "Pacific Connect",
            "flight_number": "PC221",
            "departure": f"{label} 11:05",
            "arrival": f"{label} 20:05",
            "duration": "9h 00m",
            "price_per_person": float(base_price + 95),
        },
        {
            "airline": "Global Wings",
            "flight_number": "GW410",
            "departure": f"{label} 22:10",
            "arrival": f"{label} 07:10+1",
            "duration": "9h 00m",
            "price_per_person": float(base_price - 35),
        },
    ]
    return {"flights": flights}


def _compute_nights(checkin: str, checkout: str) -> int:
    try:
        nights = (
            datetime.strptime(checkout.strip(), "%Y-%m-%d")
            - datetime.strptime(checkin.strip(), "%Y-%m-%d")
        ).days
        if nights <= 0:
            return 1
        return nights
    except ValueError:
        return 4


def _search_hotels(destination: str, checkin: str, checkout: str) -> dict[str, list[dict[str, Any]]]:
    """Return deterministic mock hotel options."""
    nights = _compute_nights(checkin, checkout)
    base = 85 + ((len(destination.strip()) * 11) % 70)

    hotels = [
        {
            "name": f"{destination.strip().title()} Central Inn",
            "stars": 3,
            "price_per_night": float(base),
            "total_price": float(base * nights),
            "description": "Reliable budget-friendly hotel near transit.",
        },
        {
            "name": f"{destination.strip().title()} Riverside Hotel",
            "stars": 4,
            "price_per_night": float(base + 70),
            "total_price": float((base + 70) * nights),
            "description": "Comfort-focused stay with city access.",
        },
        {
            "name": f"{destination.strip().title()} Grand Palace",
            "stars": 5,
            "price_per_night": float(base + 165),
            "total_price": float((base + 165) * nights),
            "description": "Luxury property with premium amenities.",
        },
    ]
    return {"hotels": hotels}


def _calculate_total_cost(flight_price: float, hotel_total: float, num_travelers: int) -> dict[str, Any]:
    """Calculate deterministic trip total with fixed tax/fees rule."""
    flights_total = round(float(flight_price) * int(num_travelers), 2)
    hotels_total = round(float(hotel_total), 2)
    subtotal = flights_total + hotels_total
    taxes_and_fees = round(subtotal * 0.12, 2)
    grand_total = round(subtotal + taxes_and_fees, 2)

    return {
        "flights_total": flights_total,
        "hotels_total": hotels_total,
        "taxes_and_fees": taxes_and_fees,
        "grand_total": grand_total,
        "breakdown": (
            f"Flights (${flights_total}) + Hotels (${hotels_total}) + "
            f"Taxes/Fees 12% (${taxes_and_fees}) = ${grand_total}"
        ),
    }


@mcp.tool()
def search_flights(origin: str, destination: str, date: str) -> dict[str, list[dict[str, Any]]]:
    """Return deterministic mock flight options."""
    return _search_flights(origin, destination, date)


@mcp.tool()
def search_hotels(destination: str, checkin: str, checkout: str) -> dict[str, list[dict[str, Any]]]:
    """Return deterministic mock hotel options."""
    return _search_hotels(destination, checkin, checkout)


@mcp.tool()
def calculate_total_cost(flight_price: float, hotel_total: float, num_travelers: int) -> dict[str, Any]:
    """Calculate deterministic trip total with fixed tax/fees rule."""
    return _calculate_total_cost(flight_price, hotel_total, num_travelers)


@mcp.custom_route("/tools", methods=["GET"], include_in_schema=False)
async def tools_route(_: Request) -> JSONResponse:
    """Compatibility endpoint for PRD smoke checks."""
    tools = await mcp.get_tools()
    payload = [
        {"name": name, "description": tool.description}
        for name, tool in tools.items()
    ]
    return JSONResponse(payload)


if __name__ == "__main__":
    port = int(os.getenv("TRANSPORT_TOOLS_PORT", "8002"))
    mcp.run(transport="http", host="0.0.0.0", port=port)
