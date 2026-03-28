import sys

from agents.itinerary import __main__ as itinerary_cli


def test_parse_args_includes_verbose(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.itinerary", "Plan a trip to Paris", "--verbose"],
    )
    args = itinerary_cli.parse_args()
    assert args.request == "Plan a trip to Paris"
    assert args.verbose is True


def test_main_success_exit_code(monkeypatch, capsys) -> None:
    class DummyCrew:
        def __init__(self, verbose: bool = False):
            self.verbose = verbose

        def run(self, user_request: str) -> str:
            assert self.verbose is True
            assert user_request == "Plan a trip to Paris"
            return "ok"

    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m agents.itinerary", "Plan a trip to Paris", "--verbose"],
    )
    monkeypatch.setattr(itinerary_cli, "ItineraryBuilderCrew", DummyCrew)

    assert itinerary_cli.main() == 0
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
        ["python -m agents.itinerary", "Plan a trip to Paris"],
    )
    monkeypatch.setattr(itinerary_cli, "ItineraryBuilderCrew", FailingCrew)

    assert itinerary_cli.main() == 1
    assert "Error: boom" in capsys.readouterr().err
