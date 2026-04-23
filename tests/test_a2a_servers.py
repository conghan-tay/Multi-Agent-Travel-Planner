from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from a2a_servers import budget_server, itinerary_server, runtime, scout_server


def test_itinerary_agent_card_metadata():
    client = TestClient(itinerary_server.app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "itinerary_specialist"
    assert payload["description"]
    assert payload["skills"]


def test_scout_agent_card_metadata():
    client = TestClient(scout_server.app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "flight_hotel_specialist"
    assert payload["description"]
    assert payload["skills"]


def test_budget_agent_card_metadata():
    client = TestClient(budget_server.app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "budget_specialist"
    assert payload["description"]
    assert payload["skills"]


def test_specialist_runner_wiring(monkeypatch):
    calls: list[tuple[str, str]] = []

    class DummyItinerary:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            calls.append(("itinerary", user_request))
            return "itinerary ok"

    class DummyScout:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            calls.append(("scout", user_request))
            return "scout ok"

    class DummyBudget:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            calls.append(("budget", user_request))
            return "budget ok"

    monkeypatch.setattr(itinerary_server, "ItineraryBuilderCrew", DummyItinerary)
    monkeypatch.setattr(scout_server, "FlightHotelScoutCrew", DummyScout)
    monkeypatch.setattr(budget_server, "BudgetOptimizerCrew", DummyBudget)

    assert itinerary_server.run_itinerary_specialist("a") == "itinerary ok"
    assert scout_server.run_scout_specialist("b") == "scout ok"
    assert budget_server.run_budget_specialist("c") == "budget ok"
    assert calls == [("itinerary", "a"), ("scout", "b"), ("budget", "c")]


def test_runtime_bridge_forwards_execute_and_cancel(monkeypatch):
    calls: list[str] = []

    async def fake_execute(agent, context, event_queue):
        calls.append("execute")

    async def fake_cancel(context, event_queue):
        calls.append("cancel")

    monkeypatch.setattr(runtime, "execute_task", fake_execute)
    monkeypatch.setattr(runtime, "cancel_task", fake_cancel)

    bridge = runtime.CrewAIA2AExecutorBridge(adapter_agent=object())
    asyncio.run(bridge.execute(context=object(), event_queue=object()))
    asyncio.run(bridge.cancel(context=object(), event_queue=object()))
    assert calls == ["execute", "cancel"]


def test_runtime_build_app_uses_default_spec_port_in_card_url():
    spec = runtime.SpecialistServerSpec(
        specialist_id="demo_specialist",
        display_name="Demo Specialist",
        description="demo",
        port=9555,
        skills=[],
    )
    app = runtime.build_app(spec=spec, runner=lambda _: "ok")
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "http://127.0.0.1:9555"


def test_runtime_build_app_uses_host_port_override_in_card_url():
    spec = runtime.SpecialistServerSpec(
        specialist_id="demo_specialist",
        display_name="Demo Specialist",
        description="demo",
        port=9555,
        skills=[],
    )
    app = runtime.build_app(
        spec=spec,
        runner=lambda _: "ok",
        host="0.0.0.0",
        port=9999,
    )
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "http://0.0.0.0:9999"
