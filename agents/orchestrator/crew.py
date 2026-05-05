"""Step 6: TravelOrchestratorCrew using A2A specialist delegation only."""

from __future__ import annotations

import os
from dataclasses import dataclass

from crewai import Agent, Crew, Process, Task
from crewai.a2a.config import A2AClientConfig

ITINERARY_AGENT_CARD_URL = "http://127.0.0.1:9001/.well-known/agent-card.json"
SCOUT_AGENT_CARD_URL = "http://127.0.0.1:9002/.well-known/agent-card.json"
BUDGET_AGENT_CARD_URL = "http://127.0.0.1:9003/.well-known/agent-card.json"
DEFAULT_A2A_ENDPOINTS = (
    ITINERARY_AGENT_CARD_URL,
    SCOUT_AGENT_CARD_URL,
    BUDGET_AGENT_CARD_URL,
)


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


@dataclass(frozen=True)
class OrchestratorConfig:
    """Runtime configuration for the travel orchestrator."""

    llm_model: str
    a2a_endpoints: tuple[str, str, str]

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        return cls(
            llm_model=_resolve_llm_model(),
            a2a_endpoints=DEFAULT_A2A_ENDPOINTS,
        )


def build_a2a_client_configs(
    endpoints: tuple[str, str, str],
) -> list[A2AClientConfig]:
    """Build the specialist A2A client configs used by the orchestrator."""
    return [
        A2AClientConfig(
            endpoint=endpoints[0],
            timeout=180,
            max_turns=3,
            accepted_output_modes=["text/plain", "application/json"],
        ),
        A2AClientConfig(
            endpoint=endpoints[1],
            timeout=180,
            max_turns=3,
            accepted_output_modes=["text/plain", "application/json"],
        ),
        A2AClientConfig(
            endpoint=endpoints[2],
            timeout=180,
            max_turns=3,
            accepted_output_modes=["text/plain", "application/json"],
        ),
    ]


class TravelOrchestratorCrew:
    """Root travel planner that routes requests to remote A2A specialists."""

    def __init__(
        self,
        verbose: bool = False,
        config: OrchestratorConfig | None = None,
    ):
        self.verbose = verbose
        self.config = config or OrchestratorConfig.from_env()
        self.llm_model = self.config.llm_model
        self.crew = self._build_crew()

    def _build_crew(self) -> Crew:
        orchestrator_agent = Agent(
            role="Travel Planning Orchestrator",
            goal=(
                "Analyze each user travel request, select the best remote specialist "
                "from the available A2A Agent Cards, and delegate the work via A2A. "
                "Never fulfill itinerary, flight, hotel, or budget work directly."
            ),
            backstory=(
                "You are a senior travel consultant at a boutique agency. You know "
                "which specialist handles itinerary building, flight and hotel search, "
                "and budget optimization. You coordinate the handoff and return the "
                "specialist's result to the user."
            ),
            llm=self.llm_model,
            verbose=self.verbose,
            a2a=build_a2a_client_configs(self.config.a2a_endpoints),
        )

        route_request_task = Task(
            name="route_request_to_specialist_task",
            description=(
                "User request: {user_request}\n\n"
                "Choose exactly one remote A2A specialist from the Agent Cards. "
                "Use itinerary_specialist for destination research and day-by-day "
                "trip plans, flight_hotel_specialist for flights, hotels, and package "
                "search, and budget_specialist for optimizing a package against a "
                "specific budget. Do not answer the travel request yourself. "
                "Delegate the full user request via A2A, then return the specialist "
                "response clearly to the user."
            ),
            expected_output=(
                "The selected remote specialist's answer, with no direct travel "
                "planning performed by the orchestrator."
            ),
            agent=orchestrator_agent,
        )

        return Crew(
            name="travel_orchestrator_crew",
            process=Process.sequential,
            agents=[orchestrator_agent],
            tasks=[route_request_task],
            verbose=self.verbose,
        )

    def run(self, user_request: str) -> str:
        result = self.crew.kickoff(inputs={"user_request": user_request})
        return str(result)
