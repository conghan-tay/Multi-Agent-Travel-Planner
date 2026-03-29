import pytest
from crewai import Process

import agents.scout.crew as scout_crew_module
from agents.scout.crew import _resolve_llm_model


def test_resolve_llm_model_openai_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert _resolve_llm_model() == "gpt-4o-mini"


def test_resolve_llm_model_anthropic_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert _resolve_llm_model() == "claude-sonnet-4-6"


def test_resolve_llm_model_raises_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="LLM is not configured"):
        _resolve_llm_model()


def test_scout_crew_structure_async_tasks_and_context(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCrew:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setattr(scout_crew_module, "Crew", FakeCrew)

    scout = scout_crew_module.FlightHotelScoutCrew(verbose=False)
    crew = scout.crew

    assert crew.process == Process.sequential
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3

    task_names = [task.name for task in crew.tasks]
    assert task_names == [
        "search_flights_task",
        "search_hotels_task",
        "merge_results_task",
    ]

    assert crew.tasks[0].async_execution is True
    assert crew.tasks[1].async_execution is True
    assert [task.name for task in crew.tasks[2].context] == [
        "search_flights_task",
        "search_hotels_task",
    ]
