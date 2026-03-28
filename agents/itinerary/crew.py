"""Step 2: ItineraryBuilderCrew (strict sequential workflow)."""

from __future__ import annotations

import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv

from .tools import get_destination_info_tool, get_local_events_tool


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


class ItineraryBuilderCrew:
    """Builds destination itineraries using a sequential 3-agent pipeline."""

    def __init__(self, verbose: bool = False):
        load_dotenv(override=True)
        self.verbose = verbose
        self.llm_model = _resolve_llm_model()
        self.crew = self._build_crew()

    def _build_crew(self) -> Crew:
        destination_research_agent = Agent(
            role="Destination Research Specialist",
            goal=(
                "Create a destination brief with climate, attractions, visa guidance, "
                "and month-specific events for itinerary planning."
            ),
            backstory=(
                "You are a methodical travel researcher. You always call both "
                "get_destination_info and get_local_events before writing your brief."
            ),
            tools=[get_destination_info_tool, get_local_events_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        itinerary_draft_agent = Agent(
            role="Itinerary Architect",
            goal=(
                "Create a logical day-by-day itinerary from the destination brief "
                "without calling tools."
            ),
            backstory=(
                "You are a veteran planner focused on realistic daily pacing and "
                "geographic efficiency."
            ),
            llm=self.llm_model,
            verbose=self.verbose,
        )

        itinerary_formatter_agent = Agent(
            role="Travel Document Editor",
            goal="Format the itinerary into a polished, client-ready trip plan.",
            backstory=(
                "You are an editor focused on clarity, consistent formatting, "
                "and practical usability."
            ),
            llm=self.llm_model,
            verbose=self.verbose,
        )

        research_destination_task = Task(
            name="research_destination_task",
            description=(
                "Research the user's request: {user_request}. "
                "Derive destination and travel month from the request. "
                "Call get_destination_info(destination), then call "
                "get_local_events(destination, month). "
                "Return a structured destination brief with: destination + month, "
                "climate summary, top attractions, visa notes, and local events."
            ),
            expected_output=(
                "Structured destination brief with sections: Destination & Month, "
                "Climate, Attractions, Visa, Local Events."
            ),
            agent=destination_research_agent,
        )

        draft_itinerary_task = Task(
            name="draft_itinerary_task",
            description=(
                "Using the destination brief from context and user request "
                "{user_request}, produce a raw day-by-day itinerary. "
                "Each day must include Morning, Afternoon, and Evening activity blocks "
                "with estimated durations and practical notes."
            ),
            expected_output=(
                "Raw itinerary by day, including morning/afternoon/evening blocks, "
                "duration estimates, and practical notes."
            ),
            agent=itinerary_draft_agent,
            context=[research_destination_task],
        )

        format_itinerary_task = Task(
            name="format_itinerary_task",
            description=(
                "Format the raw itinerary from context into a polished final output. "
                "Do not add new facts. Keep this exact structure: "
                "1) 2-3 sentence trip introduction, "
                "2) Day-by-day sections with Morning / Afternoon / Evening headings, "
                "3) Practical Notes section."
            ),
            expected_output=(
                "A polished trip plan with introduction, clearly labeled day sections, "
                "and a Practical Notes section."
            ),
            agent=itinerary_formatter_agent,
            context=[draft_itinerary_task],
        )

        return Crew(
            name="itinerary_builder_crew",
            process=Process.sequential,
            agents=[
                destination_research_agent,
                itinerary_draft_agent,
                itinerary_formatter_agent,
            ],
            tasks=[
                research_destination_task,
                draft_itinerary_task,
                format_itinerary_task,
            ],
            verbose=self.verbose,
        )

    def run(self, user_request: str) -> str:
        result = self.crew.kickoff(inputs={"user_request": user_request})
        return str(result)
