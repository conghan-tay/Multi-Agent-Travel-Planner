"""CrewAI tools for calling pricing-db-tools via FastMCP."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from crewai.tools import tool
from fastmcp import Client

PRICING_DB_TOOLS_URL = os.getenv("PRICING_DB_TOOLS_URL", "http://127.0.0.1:8003/mcp")


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

        raise RuntimeError(f"Unexpected response payload from pricing-db-tools for `{name}`")


def _run_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return asyncio.run(_call_pricing_tool(name=name, arguments=arguments))
    except Exception as exc:
        raise RuntimeError(
            "Unable to reach pricing-db-tools at "
            f"{PRICING_DB_TOOLS_URL}. Start services with `make start-tools` "
            "and verify `curl http://127.0.0.1:8003/tools`."
        ) from exc


@tool("lookup_avg_price")
def lookup_avg_price_tool(destination: str, travel_type: str) -> dict[str, Any]:
    """Looks up the historical average price for a travel component."""
    return _run_tool_call(
        "lookup_avg_price",
        {"destination": destination, "travel_type": travel_type},
    )


@tool("get_budget_tiers")
def get_budget_tiers_tool(destination: str) -> dict[str, Any]:
    """Returns budget, mid-range, and luxury tiers for a destination."""
    return _run_tool_call("get_budget_tiers", {"destination": destination})
