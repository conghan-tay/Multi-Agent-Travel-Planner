"""A2A server wrapper for Step-3 FlightHotelScoutCrew."""

from __future__ import annotations

from a2a.types import AgentSkill
from dotenv import load_dotenv

from agents.scout import FlightHotelScoutCrew

from .runtime import SpecialistServerSpec, build_app, run_specialist_server

SPEC = SpecialistServerSpec(
    specialist_id="flight_hotel_specialist",
    display_name="Flight and Hotel Specialist",
    description=(
        "Finds flight and hotel options in parallel and returns merged travel packages "
        "with total costs."
    ),
    port=9002,
    skills=[
        AgentSkill(
            id="search_flights_hotels",
            name="Search Flights and Hotels",
            description="Search and merge flight and hotel options into package recommendations.",
            tags=["flights", "hotels", "parallel", "packages"],
        ),
    ],
)


async def run_scout_specialist(user_request: str) -> str:
    return await FlightHotelScoutCrew(verbose=False).run_async(user_request)


def make_app():
    load_dotenv(override=True)
    return build_app(spec=SPEC, runner=run_scout_specialist)


def main() -> None:
    run_specialist_server(
        spec=SPEC,
        runner=run_scout_specialist,
        program_name="python -m a2a_servers.scout_server",
    )


if __name__ == "__main__":
    main()
