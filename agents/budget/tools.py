"""CrewAI tools/utilities for budget specialist tool-server access."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from crewai.tools import tool
from fastmcp import Client

PRICING_DB_TOOLS_URL = os.getenv("PRICING_DB_TOOLS_URL", "http://127.0.0.1:8003/mcp")
TRANSPORT_TOOLS_URL = os.getenv("TRANSPORT_TOOLS_URL", "http://127.0.0.1:8002/mcp")

_HOTEL_TIER_TO_TRAVEL_TYPE = {
    "budget": "hotel_budget",
    "midrange": "hotel_midrange",
    "luxury": "hotel_luxury",
}


async def _call_pricing_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(PRICING_DB_TOOLS_URL) as client:
        result = await client.call_tool(name, arguments)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"pricing-db-tools returned an error for `{name}`")

        data = getattr(result, "data", None)
        if isinstance(data, dict):
            return data

        structured_content = getattr(result, "structured_content", None)
        if isinstance(structured_content, dict):
            return structured_content

        raise RuntimeError(
            f"Unexpected response payload from pricing-db-tools for `{name}`"
        )


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

        raise RuntimeError(
            f"Unexpected response payload from transport-tools for `{name}`"
        )


def _run_pricing_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return asyncio.run(_call_pricing_tool(name=name, arguments=arguments))
    except Exception as exc:
        raise RuntimeError(
            "Unable to reach pricing-db-tools at "
            f"{PRICING_DB_TOOLS_URL}. Start services with `make start-tools` "
            "and verify `curl http://127.0.0.1:8003/tools`."
        ) from exc


def _run_transport_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return asyncio.run(_call_transport_tool(name=name, arguments=arguments))
    except Exception as exc:
        raise RuntimeError(
            "Unable to reach transport-tools at "
            f"{TRANSPORT_TOOLS_URL}. Start services with `make start-tools` "
            "and verify `curl http://127.0.0.1:8002/tools`."
        ) from exc


def lookup_avg_price_raw(destination: str, travel_type: str) -> dict[str, Any]:
    """Internal raw wrapper for pricing-db lookup_avg_price."""
    return _run_pricing_tool_call(
        "lookup_avg_price",
        {"destination": destination, "travel_type": travel_type},
    )


@tool("lookup_avg_flight_price")
def lookup_avg_flight_price_tool(destination: str) -> dict[str, Any]:
    """Looks up historical average flight price for a destination."""
    return lookup_avg_price_raw(destination=destination, travel_type="flight")


@tool("lookup_avg_hotel_price")
def lookup_avg_hotel_price_tool(destination: str, tier: str = "midrange") -> dict[str, Any]:
    """Looks up historical average hotel price for a destination and tier."""
    normalized_tier = tier.strip().lower()
    if normalized_tier not in _HOTEL_TIER_TO_TRAVEL_TYPE:
        raise ValueError("tier must be one of: budget, midrange, luxury")

    travel_type = _HOTEL_TIER_TO_TRAVEL_TYPE[normalized_tier]
    return lookup_avg_price_raw(destination=destination, travel_type=travel_type)


@tool("get_budget_tiers")
def get_budget_tiers_tool(destination: str) -> dict[str, Any]:
    """Returns budget, mid-range, and luxury tiers for a destination."""
    return _run_pricing_tool_call("get_budget_tiers", {"destination": destination})


def calculate_total_cost_transport(
    flight_price: float,
    hotel_total: float,
    num_travelers: int,
) -> dict[str, Any]:
    """Deterministically computes package total via transport-tools."""
    return _run_transport_tool_call(
        "calculate_total_cost",
        {
            "flight_price": float(flight_price),
            "hotel_total": float(hotel_total),
            "num_travelers": int(num_travelers),
        },
    )
