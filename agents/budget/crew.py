"""Step 4: BudgetOptimizerCrew implemented with strict schema + Flow router loop."""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, listen, router, start
from crewai.tasks.task_output import TaskOutput
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .tools import (
    calculate_total_cost_transport,
    get_budget_tiers_tool,
    lookup_avg_flight_price_tool,
    lookup_avg_hotel_price_tool,
)

VALIDATION_ERROR_PREFIX = "Validation error"


class BudgetContextPayload(BaseModel):
    is_valid: bool = True
    reason: str = ""
    origin: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    target_budget: float
    traveler_count: int
    trip_nights: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    flight_price_per_person: float
    hotel_total: float
    current_total_estimate: float | None = None
    package_summary: str | None = None

    @field_validator("target_budget", "flight_price_per_person", "hotel_total")
    @classmethod
    def _positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return float(value)

    @field_validator("traveler_count")
    @classmethod
    def _positive_travelers(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return int(value)

    @field_validator("trip_nights")
    @classmethod
    def _positive_nights(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("must be greater than 0")
        return int(value) if value is not None else None

    @model_validator(mode="after")
    def _cross_validate(self) -> "BudgetContextPayload":
        if not self.is_valid:
            message = self.reason.strip() or "validator marked input as invalid"
            raise ValueError(message)

        if self.start_date and self.end_date:
            nights_from_dates = (self.end_date - self.start_date).days
            if nights_from_dates <= 0:
                raise ValueError("end_date must be after start_date")
            if self.trip_nights is None:
                self.trip_nights = nights_from_dates
            elif self.trip_nights != nights_from_dates:
                raise ValueError(
                    "trip_nights is inconsistent with start_date/end_date"
                )

        if self.trip_nights is None:
            raise ValueError(
                "trip_nights is required unless start_date and end_date are provided"
            )

        return self


class BudgetOptimizerState(BaseModel):
    user_request: str = ""
    origin: str = ""
    destination: str = ""
    target_budget: float = 0.0
    current_cost: float = 0.0
    current_plan: str = ""
    traveler_count: int = 1
    trip_nights: int = 1
    iteration_count: int = 0
    max_iterations: int = 3
    savings_log: list[str] = Field(default_factory=list)
    validation_error: str | None = None


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


def _parse_money_value(value: str) -> float | None:
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_new_total(text: str) -> float | None:
    match = re.search(
        r"\*{0,2}\s*New\s+Estimated\s+Total\s*\*{0,2}\s*:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _parse_money_value(match.group(1))


class BudgetOptimizerFlow(Flow[BudgetOptimizerState]):
    """Flow that validates context and iteratively optimizes cost against budget."""

    _skip_auto_memory = True

    def __init__(self, llm_model: str, verbose: bool = False):
        super().__init__()
        object.__setattr__(self, "llm_model", llm_model)
        object.__setattr__(self, "verbose", verbose)

    @start()
    def initialize(self) -> str:
        user_request = self.state.user_request.strip()
        if not user_request:
            self.state.validation_error = (
                f"{VALIDATION_ERROR_PREFIX}: input request is empty. "
                "Required fields: origin, destination, target budget, traveler count, "
                "trip length/dates, flight price per traveler, hotel total."
            )
            return "validation_failed"

        try:
            parsed = self._validate_plan_context(user_request)
        except RuntimeError as exc:
            self.state.validation_error = str(exc)
            return "validation_failed"

        baseline_cost = self._compute_current_total_estimate(parsed)
        if baseline_cost <= 0:
            self.state.validation_error = (
                f"{VALIDATION_ERROR_PREFIX}: failed to compute package total from transport-tools"
            )
            return "validation_failed"

        self.state.origin = parsed.origin
        self.state.destination = parsed.destination
        self.state.target_budget = parsed.target_budget
        self.state.current_cost = baseline_cost
        self.state.current_plan = parsed.package_summary or user_request
        self.state.traveler_count = parsed.traveler_count
        self.state.trip_nights = parsed.trip_nights or 1
        self.state.iteration_count = 0
        self.state.savings_log = []
        self.state.validation_error = None
        return "validated"

    @router(initialize)
    def route_after_validation(self) -> str:
        if self.state.validation_error:
            return "stop"
        return "analyze"

    @listen("analyze")
    def analyze_budget(self) -> str:
        return self._run_analysis_task()

    @listen(analyze_budget)
    def adjust_plan(self, analysis_output: str) -> str:
        adjustment_output = self._run_adjustment_task(analysis_output)
        new_total = _extract_new_total(adjustment_output)
        if new_total is None:
            raise RuntimeError(
                "Plan adjustment output missing required 'New Estimated Total: $X' line."
            )

        previous_cost = self.state.current_cost
        self.state.current_cost = new_total
        self.state.iteration_count += 1
        self.state.current_plan = adjustment_output

        savings = max(previous_cost - new_total, 0.0)
        self.state.savings_log.append(
            f"Iteration {self.state.iteration_count}: saved ${savings:.2f}"
        )
        return adjustment_output

    @router(adjust_plan)
    def route_after_adjustment(self) -> str:
        if self.state.current_cost <= self.state.target_budget:
            return "stop"
        if self.state.iteration_count >= self.state.max_iterations:
            return "stop"
        return "analyze"

    @listen("stop")
    def finalize(self) -> str:
        if self.state.validation_error:
            return self.state.validation_error

        if self.state.current_cost <= self.state.target_budget:
            return (
                "Budget optimization complete: plan is within budget.\n"
                f"Target budget: ${self.state.target_budget:.2f}\n"
                f"Final estimated total: ${self.state.current_cost:.2f}\n\n"
                f"{self.state.current_plan}"
            )

        return (
            "Budget optimization stopped at max iterations.\n"
            f"Target budget: ${self.state.target_budget:.2f}\n"
            f"Final estimated total: ${self.state.current_cost:.2f}\n\n"
            f"{self.state.current_plan}"
        )

    def _validate_plan_context(self, user_request: str) -> BudgetContextPayload:
        validator_agent = Agent(
            role="Travel Plan Context Validator",
            goal=(
                "Extract strict budget optimization fields from user input in valid JSON."
            ),
            backstory=(
                "You are a strict intake validator. You return only JSON with exact fields "
                "required for travel package cost optimization."
            ),
            llm=self.llm_model,
            verbose=self.verbose,
        )

        

        validation_task = Task(
            name="validate_budget_context_task",
            description=(
                "Evaluate user request: {user_request}. "
                "Extract these required fields: origin, destination, target_budget, "
                "traveler_count, flight_price_per_person, hotel_total.\n"
                "Optional keys: trip_nights, start_date, end_date, package_summary.\n"
                "This contract supports ONE flight price and ONE hotel total only.\n"
                "Set is_valid=True when no required fields are missing. ELSE set is_valid=False and set the reason why in reason field"
            ),
            expected_output="A structured BudgetContextPayload output.",
            output_pydantic=BudgetContextPayload,
            agent=validator_agent,
        )

        validator_crew = Crew(
            name="budget_context_validator_crew",
            process=Process.sequential,
            agents=[validator_agent],
            tasks=[validation_task],
            verbose=self.verbose,
        )

        result = validator_crew.kickoff(inputs={"user_request": user_request})
        task_output: TaskOutput | None = getattr(result, "tasks_output", [None])[0]
        if task_output is None:
            raise RuntimeError(
                f"{VALIDATION_ERROR_PREFIX}: validator task output missing"
            )

        pydantic_output = task_output.pydantic
        if pydantic_output is None:
            raise RuntimeError(
                f"{VALIDATION_ERROR_PREFIX}: validator typed output missing"
            )

        if not isinstance(pydantic_output, BudgetContextPayload):
            raise RuntimeError(
                f"{VALIDATION_ERROR_PREFIX}: validator typed output invalid type"
            )

        try:
            return BudgetContextPayload.model_validate(pydantic_output.model_dump())
        except ValidationError as exc:
            raise RuntimeError(
                f"{VALIDATION_ERROR_PREFIX}: invalid budget context schema: {exc.errors()}"
            ) from exc

    def _compute_current_total_estimate(self, parsed: BudgetContextPayload) -> float:
        response = calculate_total_cost_transport(
            flight_price=parsed.flight_price_per_person,
            hotel_total=parsed.hotel_total,
            num_travelers=parsed.traveler_count,
        )
        grand_total = response.get("grand_total")
        if isinstance(grand_total, (int, float)):
            return float(grand_total)
        return 0.0

    def _run_analysis_task(self) -> str:
        budget_analysis_agent = Agent(
            role="Travel Budget Analyst",
            goal=(
                "Assess plan cost against budget and benchmark against destination tiers."
            ),
            backstory=(
                "You are a forensic travel budget analyst focused on concrete savings paths."
            ),
            tools=[
                lookup_avg_flight_price_tool,
                lookup_avg_hotel_price_tool,
                get_budget_tiers_tool,
            ],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        analysis_task = Task(
            name="analyze_budget_task",
            description=(
                "Analyze this plan against budget using tool calls as needed.\n"
                f"Origin: {self.state.origin}\n"
                f"Destination: {self.state.destination}\n"
                f"Current Estimated Total: ${self.state.current_cost:.2f}\n"
                f"Target Budget: ${self.state.target_budget:.2f}\n"
                f"Travelers: {self.state.traveler_count}\n"
                f"Trip Nights: {self.state.trip_nights}\n"
                f"Current Plan:\n{self.state.current_plan}\n"
                "Use lookup_avg_flight_price(destination), lookup_avg_hotel_price(destination, tier), "
                "and get_budget_tiers(destination). Do not call lookup_avg_price with arbitrary travel_type."
            ),
            expected_output=(
                "Budget Gap Analysis including current total, target budget, gap, benchmark "
                "references, and top cost-reduction actions."
            ),
            agent=budget_analysis_agent,
        )

        analysis_crew = Crew(
            name="budget_analysis_crew",
            process=Process.sequential,
            agents=[budget_analysis_agent],
            tasks=[analysis_task],
            verbose=self.verbose,
        )

        return str(analysis_crew.kickoff())

    def _run_adjustment_task(self, analysis_output: str) -> str:
        plan_adjustment_agent = Agent(
            role="Travel Plan Optimizer",
            goal=(
                "Apply concrete cost reductions and always provide a new estimated total."
            ),
            backstory=(
                "You are a tactical optimizer translating benchmark data into specific swaps."
            ),
            tools=[lookup_avg_flight_price_tool, lookup_avg_hotel_price_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        adjustment_task = Task(
            name="adjust_plan_task",
            description=(
                "Using the budget analysis below, apply 1-2 concrete adjustments.\n"
                f"Origin: {self.state.origin}\n"
                f"Destination: {self.state.destination}\n"
                f"Current Estimated Total: ${self.state.current_cost:.2f}\n"
                f"Target Budget: ${self.state.target_budget:.2f}\n"
                f"Travelers: {self.state.traveler_count}\n"
                f"Trip Nights: {self.state.trip_nights}\n"
                f"Budget Analysis:\n{analysis_output}\n"
                "Use lookup_avg_flight_price and lookup_avg_hotel_price only.\n"
                "Return the updated plan and include a parseable final line exactly like:\n"
                "New Estimated Total: $X"
            ),
            expected_output=(
                "Adjusted plan summary with named swaps, savings, and ending line "
                "'New Estimated Total: $X'."
            ),
            agent=plan_adjustment_agent,
        )

        adjustment_crew = Crew(
            name="plan_adjustment_crew",
            process=Process.sequential,
            agents=[plan_adjustment_agent],
            tasks=[adjustment_task],
            verbose=self.verbose,
        )

        return str(adjustment_crew.kickoff())


class BudgetOptimizerCrew:
    """Wrapper that runs the BudgetOptimizerFlow from a direct specialist entrypoint."""

    def __init__(self, verbose: bool = False):
        load_dotenv(override=True)
        self.verbose = verbose
        self.llm_model = _resolve_llm_model()

    def run(self, user_request: str) -> str:
        flow = BudgetOptimizerFlow(llm_model=self.llm_model, verbose=self.verbose)
        result = flow.kickoff(inputs={"user_request": user_request})
        return str(result)
