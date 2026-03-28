import pytest
from crewai import Process

import agents.itinerary.crew as itinerary_crew_module
from agents.itinerary.crew import _resolve_llm_model


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


def test_itinerary_crew_structure_and_context_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCrew:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setattr(itinerary_crew_module, "Crew", FakeCrew)

    itinerary = itinerary_crew_module.ItineraryBuilderCrew(verbose=False)
    crew = itinerary.crew

    assert crew.process == Process.sequential
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3

    task_names = [task.name for task in crew.tasks]
    assert task_names == [
        "research_destination_task",
        "draft_itinerary_task",
        "format_itinerary_task",
    ]

    assert crew.tasks[1].context[0].name == "research_destination_task"
    assert crew.tasks[2].context[0].name == "draft_itinerary_task"
