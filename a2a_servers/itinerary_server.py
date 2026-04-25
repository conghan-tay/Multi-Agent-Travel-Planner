"""A2A server wrapper for Step-2 ItineraryBuilderCrew."""

from __future__ import annotations

import asyncio

from a2a.types import AgentSkill
from dotenv import load_dotenv

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


async def run_itinerary_specialist(user_request: str) -> str:
    return await asyncio.to_thread(
        lambda: ItineraryBuilderCrew(verbose=False).run(user_request)
    )


def make_app():
    load_dotenv(override=True)
    return build_app(spec=SPEC, runner=run_itinerary_specialist)


def main() -> None:
    run_specialist_server(
        spec=SPEC,
        runner=run_itinerary_specialist,
        program_name="python -m a2a_servers.itinerary_server",
    )


if __name__ == "__main__":
    main()
