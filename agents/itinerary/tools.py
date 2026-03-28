"""CrewAI tools for calling destination-tools via FastMCP."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from crewai.tools import tool
from fastmcp import Client

DESTINATION_TOOLS_URL = os.getenv("DESTINATION_TOOLS_URL", "http://127.0.0.1:8001/mcp")


async def _call_destination_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(DESTINATION_TOOLS_URL) as client:
        result = await client.call_tool(name, arguments)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"destination-tools returned an error for `{name}`")

        data = getattr(result, "data", None)
        if isinstance(data, dict):
            return data

        structured_content = getattr(result, "structured_content", None)
        if isinstance(structured_content, dict):
            return structured_content

        raise RuntimeError(f"Unexpected response payload from destination-tools for `{name}`")


def _run_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return asyncio.run(_call_destination_tool(name=name, arguments=arguments))
    except Exception as exc:
        raise RuntimeError(
            "Unable to reach destination-tools at "
            f"{DESTINATION_TOOLS_URL}. Start services with `make start-tools` "
            "and verify `curl http://127.0.0.1:8001/tools`."
        ) from exc


@tool("get_destination_info")
def get_destination_info_tool(destination: str) -> dict[str, Any]:
    """Retrieves destination climate, attractions, visa details, and travel tips."""
    return _run_tool_call("get_destination_info", {"destination": destination})


@tool("get_local_events")
def get_local_events_tool(destination: str, month: str) -> dict[str, Any]:
    """Retrieves local events in a destination for a specific month."""
    return _run_tool_call("get_local_events", {"destination": destination, "month": month})

