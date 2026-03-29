"""CrewAI tools for calling transport-tools via FastMCP."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from crewai.tools import tool
from fastmcp import Client

TRANSPORT_TOOLS_URL = os.getenv("TRANSPORT_TOOLS_URL", "http://127.0.0.1:8002/mcp")


async def _call_transport_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(TRANSPORT_TOOLS_URL) as client:
        result = await client.call_tool(name, arguments)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"transport-tools returned an error for `{name}`")

        data = getattr(result, "data", None)
        if isinstance(data, dict):
            return data

        structured_content = getattr(result, "structured_content", None)
        if isinstance(structured_content, dict):
            return structured_content

        raise RuntimeError(f"Unexpected response payload from transport-tools for `{name}`")


def _run_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return asyncio.run(_call_transport_tool(name=name, arguments=arguments))
    except Exception as exc:
        raise RuntimeError(
            "Unable to reach transport-tools at "
            f"{TRANSPORT_TOOLS_URL}. Start services with `make start-tools` "
            "and verify `curl http://127.0.0.1:8002/tools`."
        ) from exc


@tool("search_flights")
def search_flights_tool(origin: str, destination: str, date: str) -> dict[str, Any]:
    """Retrieves flight options for a given route and date."""
    return _run_tool_call(
        "search_flights",
        {"origin": origin, "destination": destination, "date": date},
    )


@tool("search_hotels")
def search_hotels_tool(destination: str, checkin: str, checkout: str) -> dict[str, Any]:
    """Retrieves hotel options for a destination and stay window."""
    return _run_tool_call(
        "search_hotels",
        {"destination": destination, "checkin": checkin, "checkout": checkout},
    )


@tool("calculate_total_cost")
def calculate_total_cost_tool(
    flight_price: float, hotel_total: float, num_travelers: int
) -> dict[str, Any]:
    """Calculates package total cost from flight and hotel prices."""
    return _run_tool_call(
        "calculate_total_cost",
        {
            "flight_price": flight_price,
            "hotel_total": hotel_total,
            "num_travelers": num_travelers,
        },
    )
