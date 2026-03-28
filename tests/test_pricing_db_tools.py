from pathlib import Path

import pytest

from data.seed_db import seed_database
from tool_servers.pricing_db_tools.main import (
    _connect,
    _get_budget_tiers,
    _lookup_avg_price,
)


def test_lookup_avg_price_found(tmp_path: Path) -> None:
    db = tmp_path / "travel.db"
    seed_database(db)

    result = _lookup_avg_price("Tokyo", "flight", db_path=db)
    assert result["avg_price"] == 850.0
    assert result["currency"] == "USD"


def test_lookup_avg_price_missing(tmp_path: Path) -> None:
    db = tmp_path / "travel.db"
    seed_database(db)

    result = _lookup_avg_price("Atlantis", "flight", db_path=db)
    assert "error" in result
    assert result["avg_price"] == 0.0


def test_get_budget_tiers_default_for_unknown_destination(tmp_path: Path) -> None:
    db = tmp_path / "travel.db"
    seed_database(db)

    result = _get_budget_tiers("Atlantis", db_path=db)
    assert result["destination"] == "Atlantis"
    assert result["budget"] == {"hotel_per_night": None, "daily_spend": None}
    assert result["midrange"] == {"hotel_per_night": None, "daily_spend": None}
    assert result["luxury"] == {"hotel_per_night": None, "daily_spend": None}


def test_connect_raises_for_missing_db(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError, match="Database not found at"):
        _connect(missing)
