"""Step 3: FlightHotelScoutCrew with async fan-out and sequential fan-in."""

from __future__ import annotations

import asyncio
import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv

from .tools import calculate_total_cost_tool, search_flights_tool, search_hotels_tool


def _resolve_llm_model() -> str:
    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if not llm_provider:
        if os.getenv("OPENAI_API_KEY"):
            llm_provider = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            llm_provider = "anthropic"

    if llm_provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o")
    if llm_provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    raise RuntimeError(
        "LLM is not configured. Set LLM_PROVIDER=openai or anthropic in `.env`, "
        "and provide the matching API key."
    )


class FlightHotelScoutCrew:
    """Find flight and hotel options in parallel, then merge them into packages."""

    def __init__(self, verbose: bool = False):
        load_dotenv(override=True)
        self.verbose = verbose
        self.llm_model = _resolve_llm_model()
        self.crew = self._build_crew()

    def _build_crew(self) -> Crew:
        flight_search_agent = Agent(
            role="Flight Search Specialist",
            goal=(
                "Find the best flight options matching user parameters and return "
                "clear structured results for downstream merging."
            ),
            backstory=(
                "You are a flight-only specialist. You always use search_flights "
                "and return concise, structured options."
            ),
            tools=[search_flights_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        hotel_search_agent = Agent(
            role="Accommodation Search Specialist",
            goal=(
                "Find the best hotel options matching user parameters and return "
                "clear structured results for downstream merging."
            ),
            backstory=(
                "You are a hotel sourcing specialist. You always use search_hotels "
                "and return concise, structured options."
            ),
            tools=[search_hotels_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        result_merger_agent = Agent(
            role="Travel Package Analyst",
            goal=(
                "Merge flight and hotel results into value-ranked travel packages "
                "with accurate total cost calculations."
            ),
            backstory=(
                "You are the synthesis point. You call calculate_total_cost to "
                "compute package totals and recommend the best overall value."
            ),
            tools=[calculate_total_cost_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        search_flights_task = Task(
            name="search_flights_task",
            description=(
                "From user request {user_request}, extract origin, destination, "
                "departure date. Call search_flights(origin, "
                "destination, departure_date) and return results labeled "
                "'FLIGHT RESULTS'. Include airline, flight number, departure, "
                "arrival, duration, and price per person."
            ),
            expected_output=(
                "FLIGHT RESULTS with a structured list of options including airline, "
                "flight number, schedule, duration, and price per person."
            ),
            agent=flight_search_agent,
            async_execution=True,
        )

        search_hotels_task = Task(
            name="search_hotels_task",
            description=(
                "From user request {user_request}, extract destination, check-in "
                "(departure date), and check-out (return date). Call "
                "search_hotels(destination, checkin, checkout) and return results "
                "labeled 'HOTEL RESULTS'. Include hotel name, stars, "
                "price per night, total price, and a one-line description."
            ),
            expected_output=(
                "HOTEL RESULTS with a structured list of options including name, "
                "stars, per-night price, total price, and description."
            ),
            agent=hotel_search_agent,
            async_execution=True,
        )

        merge_results_task = Task(
            name="merge_results_task",
            description=(
                "Use both context inputs from FLIGHT RESULTS and HOTEL RESULTS. "
                "Build up to 3 package combinations and compute each package's "
                "total by calling calculate_total_cost(flight_price, hotel_total, "
                "num_travelers). Assume num_travelers from user request; default to "
                "2 when missing. Return a 'Travel Options Summary' ranked best "
                "overall value first, with one final recommendation and a brief "
                "justification."
            ),
            expected_output=(
                "Travel Options Summary with up to 3 numbered packages, each "
                "containing flight details, hotel details, and total cost "
                "breakdown, followed by one recommended package."
            ),
            agent=result_merger_agent,
            context=[search_flights_task, search_hotels_task],
        )

        return Crew(
            name="flight_hotel_scout_crew",
            process=Process.sequential,
            agents=[flight_search_agent, hotel_search_agent, result_merger_agent],
            tasks=[search_flights_task, search_hotels_task, merge_results_task],
            verbose=self.verbose,
        )

    async def run_async(self, user_request: str) -> str:
        result = await self.crew.kickoff_async(inputs={"user_request": user_request})
        return str(result)

    def run(self, user_request: str) -> str:
        return asyncio.run(self.run_async(user_request))
