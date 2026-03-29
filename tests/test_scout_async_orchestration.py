import asyncio
import pytest

import agents.scout.crew as scout_crew_module


def test_run_async_uses_kickoff_async_and_returns_string(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCrew:
        def __init__(self, **kwargs):
            self.tasks = kwargs["tasks"]
            self.called_inputs = None

        async def kickoff_async(self, inputs):
            self.called_inputs = inputs
            search_flights_task = self.tasks[0]
            search_hotels_task = self.tasks[1]
            merge_results_task = self.tasks[2]

            assert search_flights_task.async_execution is True
            assert search_hotels_task.async_execution is True
            assert [task.name for task in merge_results_task.context] == [
                "search_flights_task",
                "search_hotels_task",
            ]
            return "merged-output"

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setattr(scout_crew_module, "Crew", FakeCrew)

    scout = scout_crew_module.FlightHotelScoutCrew(verbose=False)
    result = asyncio.run(
        scout.run_async("Find me flights and hotels from NYC to Tokyo")
    )

    assert result == "merged-output"
    assert scout.crew.called_inputs == {
        "user_request": "Find me flights and hotels from NYC to Tokyo"
    }


def test_run_wraps_run_async_with_asyncio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setattr(
        scout_crew_module.FlightHotelScoutCrew,
        "_build_crew",
        lambda self: object(),
    )

    class DummyScoutCrew(scout_crew_module.FlightHotelScoutCrew):
        async def run_async(self, user_request: str) -> str:
            assert user_request == "Find me flights and hotels"
            return "ok-sync-wrapper"

    output = DummyScoutCrew(verbose=False).run("Find me flights and hotels")
    assert output == "ok-sync-wrapper"
