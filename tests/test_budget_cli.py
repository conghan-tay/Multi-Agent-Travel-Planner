import sys

from agents.budget import __main__ as budget_cli


def test_parse_args_includes_verbose(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.budget", "Optimize this plan under $3000", "--verbose"],
    )
    args = budget_cli.parse_args()
    assert args.request == "Optimize this plan under $3000"
    assert args.verbose is True


def test_main_success_exit_code(monkeypatch, capsys) -> None:
    class DummyCrew:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            assert self.verbose is True
            assert user_request == "Optimize this plan under $3000"
            return "ok"

    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.budget", "Optimize this plan under $3000", "--verbose"],
    )
    monkeypatch.setattr(budget_cli, "BudgetOptimizerCrew", DummyCrew)

    assert budget_cli.main() == 0
    assert capsys.readouterr().out.strip() == "ok"


def test_main_failure_exit_code(monkeypatch, capsys) -> None:
    class FailingCrew:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.budget", "Optimize this plan under $3000"],
    )
    monkeypatch.setattr(budget_cli, "BudgetOptimizerCrew", FailingCrew)

    assert budget_cli.main() == 1
    assert "Error: boom" in capsys.readouterr().err
