import sys

from agents.scout import __main__ as scout_cli


def test_parse_args_includes_verbose(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.scout", "Find flights and hotels to Tokyo", "--verbose"],
    )
    args = scout_cli.parse_args()
    assert args.request == "Find flights and hotels to Tokyo"
    assert args.verbose is True


def test_main_success_exit_code(monkeypatch, capsys) -> None:
    class DummyCrew:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            assert self.verbose is True
            assert user_request == "Find flights and hotels to Tokyo"
            return "ok"

    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.scout", "Find flights and hotels to Tokyo", "--verbose"],
    )
    monkeypatch.setattr(scout_cli, "FlightHotelScoutCrew", DummyCrew)

    assert scout_cli.main() == 0
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
        ["python -m agents.scout", "Find flights and hotels to Tokyo"],
    )
    monkeypatch.setattr(scout_cli, "FlightHotelScoutCrew", FailingCrew)

    assert scout_cli.main() == 1
    assert "Error: boom" in capsys.readouterr().err
