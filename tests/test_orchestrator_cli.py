from __future__ import annotations

from agents.orchestrator import __main__ as mod


def test_module_cli_loads_dotenv_without_override(monkeypatch, capsys):
    calls: list[tuple[str, bool]] = []
    dotenv_calls: list[bool] = []

    class DummyOrchestrator:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            calls.append((user_request, self.verbose))
            return "module ok"

    monkeypatch.setattr(mod, "TravelOrchestratorCrew", DummyOrchestrator)
    monkeypatch.setattr(mod, "load_dotenv", lambda override: dotenv_calls.append(override))
    monkeypatch.setattr(
        mod.sys,
        "argv",
        ["python -m agents.orchestrator", "Plan Kyoto", "--verbose"],
    )

    assert mod.main() == 0
    assert dotenv_calls == [False]
    assert calls == [("Plan Kyoto", True)]
    assert capsys.readouterr().out == "module ok\n"
