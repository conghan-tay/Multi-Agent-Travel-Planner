from __future__ import annotations

from pathlib import Path


def test_makefile_has_step5_targets():
    makefile = Path("Makefile").read_text()
    assert "start-agents:" in makefile
    assert "check-agent-ports:" in makefile
    assert "verify-agent-cards:" in makefile
    assert "a2a_servers.itinerary_server" in makefile
    assert "a2a_servers.scout_server" in makefile
    assert "a2a_servers.budget_server" in makefile

