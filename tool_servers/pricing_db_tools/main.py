"""FastMCP server: pricing-db-tools (port 8003)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("pricing-db-tools")
DB_PATH = Path(os.getenv("TRAVEL_DB_PATH", "data/travel.db"))


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run `make seed-db` first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def lookup_avg_price(destination: str, travel_type: str) -> dict[str, Any]:
    """Look up average price by destination and travel type."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT name, travel_type, avg_price, last_updated
            FROM destinations
            WHERE lower(name) = lower(?) AND travel_type = ?
            LIMIT 1
            """,
            (destination.strip(), travel_type.strip()),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "destination": destination.strip().title(),
            "travel_type": travel_type.strip(),
            "avg_price": 0.0,
            "currency": "USD",
            "last_updated": None,
            "error": "No pricing data found for destination/travel_type.",
        }

    return {
        "destination": row["name"],
        "travel_type": row["travel_type"],
        "avg_price": float(row["avg_price"]),
        "currency": "USD",
        "last_updated": row["last_updated"],
    }


@mcp.tool()
def get_budget_tiers(destination: str) -> dict[str, Any]:
    """Return budget/midrange/luxury tiers for a destination."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT tier, hotel_per_night, daily_spend
            FROM budget_tiers
            WHERE lower(destination) = lower(?)
            """,
            (destination.strip(),),
        ).fetchall()
    finally:
        conn.close()

    response: dict[str, Any] = {"destination": destination.strip().title()}
    for tier in ("budget", "midrange", "luxury"):
        response[tier] = {"hotel_per_night": None, "daily_spend": None}

    for row in rows:
        response[row["tier"]] = {
            "hotel_per_night": float(row["hotel_per_night"]),
            "daily_spend": float(row["daily_spend"]),
        }

    return response


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
    port = int(os.getenv("PRICING_DB_TOOLS_PORT", "8003"))
    mcp.run(transport="http", host="0.0.0.0", port=port)
