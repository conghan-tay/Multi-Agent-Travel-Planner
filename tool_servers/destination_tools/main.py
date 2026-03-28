"""FastMCP server: destination-tools (port 8001)."""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("destination-tools")

_DESTINATION_DATA: dict[str, dict[str, Any]] = {
    "tokyo": {
        "destination": "Tokyo",
        "climate": {
            "season": "Temperate with distinct seasons",
            "temp_range": "10-28C",
            "notes": "Autumn is mild and generally dry; layer clothing is recommended.",
        },
        "attractions": [
            {"name": "Senso-ji Temple", "description": "Historic Buddhist temple in Asakusa.", "category": "culture"},
            {"name": "Shibuya Crossing", "description": "Iconic scramble crossing and shopping district.", "category": "urban"},
            {"name": "Tokyo Skytree", "description": "Observation tower with panoramic city views.", "category": "landmark"},
            {"name": "Meiji Shrine", "description": "Peaceful shrine complex near Harajuku.", "category": "culture"},
            {"name": "Tsukiji Outer Market", "description": "Seafood and street-food market experience.", "category": "food"},
        ],
        "visa": {"required": False, "notes": "Visa depends on passport nationality; verify before travel."},
        "tips": ["Use an IC card for metro rides.", "Reserve popular restaurants in advance."],
    },
    "paris": {
        "destination": "Paris",
        "climate": {
            "season": "Oceanic climate",
            "temp_range": "7-25C",
            "notes": "Spring/fall can be cool in mornings; bring a light jacket.",
        },
        "attractions": [
            {"name": "Eiffel Tower", "description": "Paris landmark with observation decks.", "category": "landmark"},
            {"name": "Louvre Museum", "description": "World-renowned museum and art collections.", "category": "culture"},
            {"name": "Montmartre", "description": "Historic hilltop district with artist heritage.", "category": "neighborhood"},
            {"name": "Seine Cruise", "description": "Boat cruise with city monument views.", "category": "experience"},
            {"name": "Le Marais", "description": "Trendy district with cafes and boutiques.", "category": "food"},
        ],
        "visa": {"required": False, "notes": "Schengen rules apply depending on nationality."},
        "tips": ["Book major museums ahead of time.", "Carry comfortable walking shoes."],
    },
}

_LOCAL_EVENTS: dict[tuple[str, str], list[dict[str, str]]] = {
    ("tokyo", "October"): [
        {
            "name": "Tokyo Ramen Festa",
            "dates": "Mid-October",
            "description": "Regional ramen stalls gather in one event area.",
            "relevance": "Great evening food experience.",
        },
        {
            "name": "Autumn Garden Light-Up",
            "dates": "Late October",
            "description": "Seasonal illumination at select gardens.",
            "relevance": "Best for night-time itinerary slots.",
        },
    ],
    ("paris", "October"): [
        {
            "name": "Nuit Blanche",
            "dates": "Early October",
            "description": "City-wide night arts installations.",
            "relevance": "Fits an evening cultural plan.",
        }
    ],
}


def _get_destination_info(
    destination: str,
    data: dict[str, dict[str, Any]] = _DESTINATION_DATA,
) -> dict[str, Any]:
    """Return deterministic destination profile for itinerary planning."""
    key = destination.strip().lower()
    info = data.get(key)
    if info:
        return info

    normalized = destination.strip().title()
    return {
        "destination": normalized,
        "climate": {
            "season": "Varies by season",
            "temp_range": "12-26C",
            "notes": "Use this as a generic baseline and refine with local data later.",
        },
        "attractions": [
            {"name": f"{normalized} Old Town", "description": "Historic district with local character.", "category": "culture"},
            {"name": f"{normalized} Central Market", "description": "Local food and shopping area.", "category": "food"},
            {"name": f"{normalized} Waterfront", "description": "Popular walking area for sunset views.", "category": "experience"},
        ],
        "visa": {"required": False, "notes": "Check official immigration rules for your passport."},
        "tips": ["Prebook top attractions.", "Keep one flexible day in the itinerary."],
    }


def _get_local_events(
    destination: str,
    month: str,
    events_index: dict[tuple[str, str], list[dict[str, str]]] = _LOCAL_EVENTS,
) -> dict[str, Any]:
    """Return deterministic local events for a destination and month."""
    normalized_destination = destination.strip().lower()
    normalized_month = month.strip().title()
    key = (normalized_destination, normalized_month)
    events = events_index.get(key, [])
    return {
        "destination": destination.strip().title(),
        "month": normalized_month,
        "events": events,
    }


@mcp.tool()
def get_destination_info(destination: str) -> dict[str, Any]:
    """Return deterministic destination profile for itinerary planning."""
    return _get_destination_info(destination)


@mcp.tool()
def get_local_events(destination: str, month: str) -> dict[str, Any]:
    """Return deterministic local events for a destination and month."""
    return _get_local_events(destination, month)


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
    port = int(os.getenv("DESTINATION_TOOLS_PORT", "8001"))
    mcp.run(transport="http", host="0.0.0.0", port=port)
