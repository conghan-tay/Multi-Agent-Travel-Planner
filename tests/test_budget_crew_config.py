import pytest

import agents.budget.crew as budget_crew_module
from agents.budget.crew import _resolve_llm_model


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


def test_budget_crew_runs_flow_with_user_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeFlow:
        def __init__(self, llm_model: str, verbose: bool = False):
            captured["llm_model"] = llm_model
            captured["verbose"] = verbose

        def kickoff(self, inputs):
            captured["inputs"] = inputs
            return "flow-output"

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setattr(budget_crew_module, "BudgetOptimizerFlow", FakeFlow)

    crew = budget_crew_module.BudgetOptimizerCrew(verbose=True)
    result = crew.run("Optimize under $3000")

    assert result == "flow-output"
    assert captured == {
        "llm_model": "gpt-4o",
        "verbose": True,
        "inputs": {"user_request": "Optimize under $3000"},
    }
