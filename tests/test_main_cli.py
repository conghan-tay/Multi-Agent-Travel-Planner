from __future__ import annotations

import main as mod


def test_main_one_shot_success(monkeypatch, capsys):
    calls: list[tuple[str, bool]] = []
    dotenv_calls: list[bool] = []

    class DummyOrchestrator:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            calls.append((user_request, self.verbose))
            return "ok output"

    monkeypatch.setattr(mod, "TravelOrchestratorCrew", DummyOrchestrator)
    monkeypatch.setattr(mod, "load_dotenv", lambda override: dotenv_calls.append(override))

    assert mod.main(["Plan a 5-day trip", "--verbose"]) == 0
    assert dotenv_calls == [False]
    assert calls == [("Plan a 5-day trip", True)]
    assert capsys.readouterr().out == "ok output\n"


def test_main_one_shot_exception_returns_nonzero(monkeypatch, capsys):
    dotenv_calls: list[bool] = []

    class FailingOrchestrator:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr(mod, "TravelOrchestratorCrew", FailingOrchestrator)
    monkeypatch.setattr(mod, "load_dotenv", lambda override: dotenv_calls.append(override))

    assert mod.main(["Plan a 5-day trip"]) == 1
    assert dotenv_calls == [False]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: boom\n"


def test_parse_args_accepts_verbose():
    args = mod.parse_args(["Find flights", "--verbose"])
    assert args.request == "Find flights"
    assert args.verbose is True
