from __future__ import annotations

import importlib
import sys

from crewai.a2a.config import A2AClientConfig

from agents.orchestrator import crew as mod
from agents.orchestrator.crew import OrchestratorConfig, TravelOrchestratorCrew


class FakeCrew:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def kickoff(self, inputs):
        self.inputs = inputs
        return "fake output"


def test_orchestrator_configures_three_a2a_clients(monkeypatch):
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    config = OrchestratorConfig(
        llm_model="gpt-test",
        a2a_endpoints=(
            "http://127.0.0.1:9101/.well-known/agent-card.json",
            "http://127.0.0.1:9102/.well-known/agent-card.json",
            "http://127.0.0.1:9103/.well-known/agent-card.json",
        ),
    )
    orchestrator = TravelOrchestratorCrew(verbose=True, config=config)
    agent = orchestrator.crew.agents[0]

    assert agent.verbose is True
    assert orchestrator.llm_model == "gpt-test"
    assert len(agent.a2a) == 3
    assert all(isinstance(config, A2AClientConfig) for config in agent.a2a)
    assert [config.endpoint for config in agent.a2a] == [
        "http://127.0.0.1:9101/.well-known/agent-card.json",
        "http://127.0.0.1:9102/.well-known/agent-card.json",
        "http://127.0.0.1:9103/.well-known/agent-card.json",
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
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    orchestrator = TravelOrchestratorCrew(
        config=OrchestratorConfig(
            llm_model="gpt-test",
            a2a_endpoints=mod.DEFAULT_A2A_ENDPOINTS,
        )
    )
    agent = orchestrator.crew.agents[0]
    task = orchestrator.crew.tasks[0]

    assert "delegate" in agent.goal.lower()
    assert "never fulfill" in agent.goal.lower()
    assert "directly" in agent.goal.lower()
    assert "choose exactly one remote a2a specialist" in task.description.lower()
    assert "do not answer the travel request yourself" in task.description.lower()


def test_orchestrator_run_kicks_off_with_user_request(monkeypatch):
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    calls: list[dict[str, str]] = []

    class DummyCrew:
        def kickoff(self, inputs):
            calls.append(inputs)
            return "orchestrated output"

    orchestrator = TravelOrchestratorCrew(
        config=OrchestratorConfig(
            llm_model="gpt-test",
            a2a_endpoints=mod.DEFAULT_A2A_ENDPOINTS,
        )
    )
    orchestrator.crew = DummyCrew()

    assert orchestrator.run("Plan Tokyo") == "orchestrated output"
    assert calls == [{"user_request": "Plan Tokyo"}]


def test_orchestrator_config_from_env_respects_monkeypatch(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-env-test")

    config = OrchestratorConfig.from_env()

    assert config.llm_model == "gpt-env-test"
    assert config.a2a_endpoints == mod.DEFAULT_A2A_ENDPOINTS


def test_build_a2a_client_configs_uses_configured_endpoints():
    endpoints = (
        "http://127.0.0.1:9201/.well-known/agent-card.json",
        "http://127.0.0.1:9202/.well-known/agent-card.json",
        "http://127.0.0.1:9203/.well-known/agent-card.json",
    )

    configs = mod.build_a2a_client_configs(endpoints)

    assert [config.endpoint for config in configs] == list(endpoints)


def test_orchestrator_constructor_has_no_dotenv_side_effect(monkeypatch):
    monkeypatch.setattr(mod, "Crew", FakeCrew)
    assert not hasattr(mod, "load_dotenv")

    config = OrchestratorConfig(
        llm_model="gpt-explicit",
        a2a_endpoints=mod.DEFAULT_A2A_ENDPOINTS,
    )
    orchestrator = TravelOrchestratorCrew(config=config)

    assert orchestrator.llm_model == "gpt-explicit"
