"""A2A server wrapper for Step-2 ItineraryBuilderCrew."""

from __future__ import annotations

from a2a.types import AgentSkill

from agents.itinerary import ItineraryBuilderCrew

from .runtime import SpecialistServerSpec, build_app, run_specialist_server

SPEC = SpecialistServerSpec(
    specialist_id="itinerary_specialist",
    display_name="Itinerary Specialist",
    description=(
        "Builds destination-specific day-by-day itineraries with destination research, "
        "drafting, and formatting."
    ),
    port=9001,
    skills=[
        AgentSkill(
            id="build_itinerary",
            name="Build Itinerary",
            description="Create a complete day-by-day travel itinerary from a user request.",
            tags=["itinerary", "trip-plan", "sequential"],
        ),
    ],
)


def run_itinerary_specialist(user_request: str) -> str:
    return ItineraryBuilderCrew(verbose=False).run(user_request)


app = build_app(spec=SPEC, runner=run_itinerary_specialist)


def main() -> None:
    run_specialist_server(spec=SPEC, runner=run_itinerary_specialist, program_name="python -m a2a_servers.itinerary_server")


if __name__ == "__main__":
    main()

