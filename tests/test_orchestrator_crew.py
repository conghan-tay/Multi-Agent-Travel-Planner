from __future__ import annotations

import importlib
import sys

from crewai.a2a.config import A2AClientConfig

from agents.orchestrator import crew as mod
from agents.orchestrator.crew import TravelOrchestratorCrew


class FakeCrew:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def kickoff(self, inputs):
        self.inputs = inputs
        return "fake output"


def test_orchestrator_configures_three_a2a_clients(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    orchestrator = TravelOrchestratorCrew(verbose=True)
    agent = orchestrator.crew.agents[0]

    assert agent.verbose is True
    assert len(agent.a2a) == 3
    assert all(isinstance(config, A2AClientConfig) for config in agent.a2a)
    assert [config.endpoint for config in agent.a2a] == [
        mod.ITINERARY_AGENT_CARD_URL,
        mod.SCOUT_AGENT_CARD_URL,
        mod.BUDGET_AGENT_CARD_URL,
    ]


def test_orchestrator_module_does_not_import_specialist_crews(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    for name in [
        "agents.itinerary.crew",
        "agents.scout.crew",
        "agents.budget.crew",
    ]:
        sys.modules.pop(name, None)

    importlib.reload(mod)

    assert "agents.itinerary.crew" not in sys.modules
    assert "agents.scout.crew" not in sys.modules
    assert "agents.budget.crew" not in sys.modules


def test_orchestrator_prompt_requires_a2a_delegation(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    orchestrator = TravelOrchestratorCrew()
    agent = orchestrator.crew.agents[0]
    task = orchestrator.crew.tasks[0]

    assert "delegate" in agent.goal.lower()
    assert "never fulfill" in agent.goal.lower()
    assert "directly" in agent.goal.lower()
    assert "choose exactly one remote a2a specialist" in task.description.lower()
    assert "do not answer the travel request yourself" in task.description.lower()


def test_orchestrator_run_kicks_off_with_user_request(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    calls: list[dict[str, str]] = []

    class DummyCrew:
        def kickoff(self, inputs):
            calls.append(inputs)
            return "orchestrated output"

    orchestrator = TravelOrchestratorCrew()
    orchestrator.crew = DummyCrew()

    assert orchestrator.run("Plan Tokyo") == "orchestrated output"
    assert calls == [{"user_request": "Plan Tokyo"}]
