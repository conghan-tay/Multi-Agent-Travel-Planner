"""Seed SQLite database for pricing reference data (idempotent)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("data/travel.db")

DESTINATION_ROWS = [
    ("Tokyo", "flight", 850.0, "2026-03-01"),
    ("Tokyo", "hotel_budget", 95.0, "2026-03-01"),
    ("Tokyo", "hotel_midrange", 180.0, "2026-03-01"),
    ("Tokyo", "hotel_luxury", 350.0, "2026-03-01"),
    ("Paris", "flight", 780.0, "2026-03-01"),
    ("Paris", "hotel_budget", 110.0, "2026-03-01"),
    ("Paris", "hotel_midrange", 210.0, "2026-03-01"),
    ("Paris", "hotel_luxury", 420.0, "2026-03-01"),
    ("New York", "flight", 320.0, "2026-03-01"),
    ("New York", "hotel_budget", 140.0, "2026-03-01"),
    ("New York", "hotel_midrange", 260.0, "2026-03-01"),
    ("New York", "hotel_luxury", 520.0, "2026-03-01"),
    ("Singapore", "flight", 900.0, "2026-03-01"),
    ("Singapore", "hotel_budget", 85.0, "2026-03-01"),
    ("Singapore", "hotel_midrange", 170.0, "2026-03-01"),
    ("Singapore", "hotel_luxury", 320.0, "2026-03-01"),
]

BUDGET_TIER_ROWS = [
    ("Tokyo", "budget", 90.0, 55.0),
    ("Tokyo", "midrange", 180.0, 100.0),
    ("Tokyo", "luxury", 350.0, 220.0),
    ("Paris", "budget", 110.0, 70.0),
    ("Paris", "midrange", 210.0, 130.0),
    ("Paris", "luxury", 420.0, 280.0),
    ("New York", "budget", 140.0, 80.0),
    ("New York", "midrange", 260.0, 150.0),
    ("New York", "luxury", 520.0, 300.0),
    ("Singapore", "budget", 85.0, 50.0),
    ("Singapore", "midrange", 170.0, 95.0),
    ("Singapore", "luxury", 320.0, 210.0),
]


def seed_database(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS destinations (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                travel_type TEXT NOT NULL,
                avg_price REAL NOT NULL,
                last_updated TEXT,
                UNIQUE(name, travel_type)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS budget_tiers (
                id INTEGER PRIMARY KEY,
                destination TEXT NOT NULL,
                tier TEXT NOT NULL,
                hotel_per_night REAL NOT NULL,
                daily_spend REAL NOT NULL,
                UNIQUE(destination, tier)
            )
            """
        )

        cur.executemany(
            """
            INSERT INTO destinations (name, travel_type, avg_price, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name, travel_type) DO UPDATE SET
                avg_price = excluded.avg_price,
                last_updated = excluded.last_updated
            """,
            DESTINATION_ROWS,
        )

        cur.executemany(
            """
            INSERT INTO budget_tiers (destination, tier, hotel_per_night, daily_spend)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(destination, tier) DO UPDATE SET
                hotel_per_night = excluded.hotel_per_night,
                daily_spend = excluded.daily_spend
            """,
            BUDGET_TIER_ROWS,
        )

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
    print(f"Seeded database: {DB_PATH}")
