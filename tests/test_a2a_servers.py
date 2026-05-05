from __future__ import annotations

import asyncio
import logging

from fastapi.testclient import TestClient

from a2a.types import AgentSkill, Message, Part, TextPart
from a2a_servers import budget_server, itinerary_server, runtime, scout_server


def test_itinerary_agent_card_metadata():
    client = TestClient(itinerary_server.make_app())
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "itinerary_specialist"
    assert payload["description"]
    assert payload["skills"]


def test_scout_agent_card_metadata():
    client = TestClient(scout_server.make_app())
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "flight_hotel_specialist"
    assert payload["description"]
    assert payload["skills"]


def test_budget_agent_card_metadata():
    client = TestClient(budget_server.make_app())
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

        async def run_async(self, user_request: str) -> str:
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

    assert asyncio.run(itinerary_server.run_itinerary_specialist("a")) == "itinerary ok"
    assert asyncio.run(scout_server.run_scout_specialist("b")) == "scout ok"
    assert asyncio.run(budget_server.run_budget_specialist("c")) == "budget ok"
    assert calls == [("itinerary", "a"), ("scout", "b"), ("budget", "c")]


def _demo_spec() -> runtime.SpecialistServerSpec:
    return runtime.SpecialistServerSpec(
        specialist_id="demo_specialist",
        display_name="Demo Specialist",
        description="demo",
        port=9555,
        skills=[
            AgentSkill(
                id="demo",
                name="Demo",
                description="Demo skill",
                tags=["demo"],
            )
        ],
    )


def test_runtime_adapter_tool_runs_async_runner_from_sync_path():
    calls: list[str] = []

    async def async_runner(user_request: str) -> str:
        await asyncio.sleep(0)
        calls.append(user_request)
        return f"async ok: {user_request}"

    agent = runtime.build_adapter_agent(spec=_demo_spec(), runner=async_runner)
    tool = agent.tools[0]

    result = tool.run(user_request="hello")

    assert result == "async ok: hello"
    assert calls == ["hello"]


def test_runtime_adapter_tool_runs_async_runner_inside_active_event_loop():
    calls: list[str] = []

    async def async_runner(user_request: str) -> str:
        await asyncio.sleep(0)
        calls.append(user_request)
        return f"async ok: {user_request}"

    async def call_sync_tool_inside_loop() -> str:
        agent = runtime.build_adapter_agent(spec=_demo_spec(), runner=async_runner)
        return agent.tools[0].run(user_request="hello")

    result = asyncio.run(call_sync_tool_inside_loop())

    assert result == "async ok: hello"
    assert calls == ["hello"]


def test_runtime_adapter_tool_logs_runner_exception(caplog):
    async def failing_runner(user_request: str) -> str:
        await asyncio.sleep(0)
        raise RuntimeError(f"boom: {user_request}")

    agent = runtime.build_adapter_agent(spec=_demo_spec(), runner=failing_runner)
    tool = agent.tools[0]

    with caplog.at_level(logging.ERROR, logger=runtime.__name__):
        result = tool.run(user_request="bad request")

    assert result == "Specialist execution failed. RuntimeError: boom: bad request"
    assert "Specialist runner failed" in caplog.text
    assert "boom: bad request" in caplog.text


def test_runtime_a2a_endpoint_can_await_async_adapter_tool(monkeypatch):
    calls: list[str] = []

    async def async_runner(user_request: str) -> str:
        await asyncio.sleep(0)
        calls.append(user_request)
        return f"async ok: {user_request}"

    async def fake_execute(agent, context, event_queue):
        text = context.message.parts[0].root.text
        result = agent.tools[0].run(user_request=text)
        await event_queue.enqueue_event(
            Message(
                messageId="response-1",
                role="agent",
                parts=[Part(root=TextPart(text=result))],
            )
        )

    monkeypatch.setattr(runtime, "execute_task", fake_execute)
    app = runtime.build_app(spec=_demo_spec(), runner=async_runner)
    client = TestClient(app)

    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "message-1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "hello"}],
                }
            },
        },
    )

    assert response.status_code == 200
    assert calls == ["hello"]
    assert "async ok: hello" in response.text
    assert "coroutine" not in response.text.lower()


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
    async def runner(_: str) -> str:
        return "ok"

    app = runtime.build_app(spec=_demo_spec(), runner=runner)
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "http://127.0.0.1:9555/a2a"


def test_runtime_build_app_uses_host_port_override_in_card_url():
    async def runner(_: str) -> str:
        return "ok"

    app = runtime.build_app(
        spec=_demo_spec(),
        runner=runner,
        host="0.0.0.0",
        port=9999,
    )
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "http://0.0.0.0:9999/a2a"
