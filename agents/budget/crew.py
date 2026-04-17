"""Step 4: BudgetOptimizerCrew implemented with CrewAI Flow and router loop."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, listen, router, start
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .tools import get_budget_tiers_tool, lookup_avg_price_tool

VALIDATION_ERROR_MESSAGE = (
    "Validation error: missing plan context for budget optimization. "
    "Please include current flight option(s), hotel option(s), trip length/dates, "
    "and traveler count, or paste an itinerary/package summary."
)


class PlanContextValidation(BaseModel):
    is_valid: bool = False
    reason: str = ""
    destination: str | None = None
    target_budget: float | None = None
    traveler_count: int | None = None
    trip_nights: int | None = None
    flight_prices_per_person: list[float] = Field(default_factory=list)
    hotel_totals: list[float] = Field(default_factory=list)
    current_total_estimate: float | None = None
    package_summary: str | None = None


class BudgetOptimizerState(BaseModel):
    user_request: str = ""
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
        r"New Estimated Total:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _parse_money_value(match.group(1))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*", "", stripped).strip()
        stripped = stripped.removesuffix("```").strip()

    try:
        loaded = json.loads(stripped)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    candidate = re.search(r"\{[\s\S]*\}", stripped)
    if not candidate:
        return None

    try:
        loaded = json.loads(candidate.group(0))
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        return None
    return None


def _parse_date_range_nights(text: str) -> int | None:
    found = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if len(found) < 2:
        return None
    try:
        start_date = datetime.strptime(found[0], "%Y-%m-%d")
        end_date = datetime.strptime(found[1], "%Y-%m-%d")
    except ValueError:
        return None

    nights = (end_date - start_date).days
    return nights if nights > 0 else None


class BudgetOptimizerFlow(Flow[BudgetOptimizerState]):
    """Flow that validates context and iteratively optimizes cost against budget."""
    _skip_auto_memory = True

    def __init__(self, llm_model: str, verbose: bool = False):
        self.llm_model = llm_model
        self.verbose = verbose
        super().__init__()

    @start()
    def initialize(self) -> str:
        user_request = self.state.user_request.strip()
        if not user_request:
            self.state.validation_error = VALIDATION_ERROR_MESSAGE
            return "validation_failed"

        parsed = self._validate_plan_context(user_request)
        if not parsed.is_valid:
            self.state.validation_error = VALIDATION_ERROR_MESSAGE
            return "validation_failed"

        if parsed.target_budget is None or parsed.target_budget <= 0:
            self.state.validation_error = (
                f"{VALIDATION_ERROR_MESSAGE} Also include a target budget (e.g., '$3000')."
            )
            return "validation_failed"

        baseline_cost = self._compute_initial_cost(parsed)
        if baseline_cost <= 0:
            self.state.validation_error = VALIDATION_ERROR_MESSAGE
            return "validation_failed"

        self.state.destination = parsed.destination or "Unknown"
        self.state.target_budget = parsed.target_budget
        self.state.current_cost = baseline_cost
        self.state.current_plan = parsed.package_summary or user_request
        self.state.traveler_count = parsed.traveler_count or 1
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

    def _validate_plan_context(self, user_request: str) -> PlanContextValidation:
        validator_agent = Agent(
            role="Travel Plan Context Validator",
            goal=(
                "Validate whether budget-optimization input includes sufficient "
                "plan/package context and extract normalized fields for downstream use."
            ),
            backstory=(
                "You are a strict intake specialist for budget optimization. You check "
                "whether the request contains concrete package details and extract them "
                "into clean structured JSON."
            ),
            llm=self.llm_model,
            verbose=self.verbose,
        )

        validation_task = Task(
            name="validate_budget_context_task",
            description=(
                "Evaluate user request: {user_request}. Return JSON only with these keys: "
                "is_valid (bool), reason (str), destination (str|null), "
                "target_budget (number|null), traveler_count (int|null), "
                "trip_nights (int|null), flight_prices_per_person (number[]), "
                "hotel_totals (number[]), current_total_estimate (number|null), "
                "package_summary (str|null).\n"
                "Validation rule: valid only if the request includes either\n"
                "1) current flight option(s), hotel option(s), trip length/dates, and traveler count,\n"
                "or 2) a pasted itinerary/package summary with enough cost detail to estimate totals.\n"
                "If budget is missing, set is_valid=false and explain in reason."
            ),
            expected_output="Valid JSON object only, no markdown fences.",
            agent=validator_agent,
        )

        validator_crew = Crew(
            name="budget_context_validator_crew",
            process=Process.sequential,
            agents=[validator_agent],
            tasks=[validation_task],
            verbose=self.verbose,
        )

        llm_output = str(validator_crew.kickoff(inputs={"user_request": user_request}))
        parsed_json = _extract_json_object(llm_output)
        if parsed_json is not None:
            return self._normalize_validation_payload(parsed_json, user_request)

        return self._heuristic_validation(user_request)

    def _normalize_validation_payload(
        self, payload: dict[str, Any], user_request: str
    ) -> PlanContextValidation:
        def _as_float_list(values: Any) -> list[float]:
            if not isinstance(values, list):
                return []
            result: list[float] = []
            for value in values:
                if isinstance(value, (int, float)):
                    if float(value) > 0:
                        result.append(float(value))
                elif isinstance(value, str):
                    parsed = _parse_money_value(value)
                    if parsed is not None and parsed > 0:
                        result.append(parsed)
            return result

        raw_nights = payload.get("trip_nights")
        trip_nights = int(raw_nights) if isinstance(raw_nights, (int, float)) and raw_nights > 0 else None

        raw_travelers = payload.get("traveler_count")
        traveler_count = (
            int(raw_travelers)
            if isinstance(raw_travelers, (int, float)) and raw_travelers > 0
            else None
        )

        raw_budget = payload.get("target_budget")
        target_budget: float | None = None
        if isinstance(raw_budget, (int, float)):
            target_budget = float(raw_budget)
        elif isinstance(raw_budget, str):
            target_budget = _parse_money_value(raw_budget)

        raw_total = payload.get("current_total_estimate")
        current_total_estimate: float | None = None
        if isinstance(raw_total, (int, float)):
            current_total_estimate = float(raw_total)
        elif isinstance(raw_total, str):
            current_total_estimate = _parse_money_value(raw_total)

        normalized = PlanContextValidation(
            is_valid=bool(payload.get("is_valid", False)),
            reason=str(payload.get("reason", "")).strip(),
            destination=(
                str(payload.get("destination")).strip()
                if isinstance(payload.get("destination"), str)
                and str(payload.get("destination")).strip()
                else None
            ),
            target_budget=target_budget,
            traveler_count=traveler_count,
            trip_nights=trip_nights,
            flight_prices_per_person=_as_float_list(payload.get("flight_prices_per_person")),
            hotel_totals=_as_float_list(payload.get("hotel_totals")),
            current_total_estimate=current_total_estimate,
            package_summary=(
                str(payload.get("package_summary")).strip()
                if isinstance(payload.get("package_summary"), str)
                and str(payload.get("package_summary")).strip()
                else user_request
            ),
        )

        if normalized.target_budget is None or normalized.target_budget <= 0:
            normalized.is_valid = False
            return normalized

        has_minimum_fields = all(
            [
                bool(normalized.flight_prices_per_person),
                bool(normalized.hotel_totals),
                normalized.trip_nights is not None,
                normalized.traveler_count is not None,
            ]
        )
        has_summary_cost = normalized.current_total_estimate is not None

        normalized.is_valid = normalized.is_valid and (has_minimum_fields or has_summary_cost)
        return normalized

    def _heuristic_validation(self, user_request: str) -> PlanContextValidation:
        request_lower = user_request.lower()

        budget_match = re.search(
            r"(?:budget(?:\s+is|\s+of)?|under|within)\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            request_lower,
        )
        target_budget = _parse_money_value(budget_match.group(1)) if budget_match else None

        travelers_match = re.search(r"(\d+)\s*(?:traveler|travellers|travelers|people|persons)", request_lower)
        traveler_count = int(travelers_match.group(1)) if travelers_match else None

        nights_match = re.search(r"(\d+)\s*(?:night|nights|day|days)", request_lower)
        trip_nights = int(nights_match.group(1)) if nights_match else _parse_date_range_nights(user_request)

        flight_prices = [
            float(match.replace(",", ""))
            for match in re.findall(r"flight[^\n$]*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", request_lower)
        ]
        hotel_totals = [
            float(match.replace(",", ""))
            for match in re.findall(r"hotel[^\n$]*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", request_lower)
        ]

        destination_match = re.search(r"(?:to|in)\s+([A-Za-z ]{2,40})", user_request)
        destination = destination_match.group(1).strip() if destination_match else None

        total_match = re.search(r"(?:total|package)\s*(?:cost|price)?\s*[:=]?\s*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", request_lower)
        current_total_estimate = (
            _parse_money_value(total_match.group(1)) if total_match else None
        )

        has_minimum_fields = bool(flight_prices and hotel_totals and traveler_count and trip_nights)
        has_summary_cost = current_total_estimate is not None

        return PlanContextValidation(
            is_valid=bool(target_budget and (has_minimum_fields or has_summary_cost)),
            reason="Heuristic fallback parser.",
            destination=destination,
            target_budget=target_budget,
            traveler_count=traveler_count,
            trip_nights=trip_nights,
            flight_prices_per_person=flight_prices,
            hotel_totals=hotel_totals,
            current_total_estimate=current_total_estimate,
            package_summary=user_request,
        )

    def _compute_initial_cost(self, parsed: PlanContextValidation) -> float:
        if parsed.current_total_estimate is not None and parsed.current_total_estimate > 0:
            return parsed.current_total_estimate

        if (
            parsed.flight_prices_per_person
            and parsed.hotel_totals
            and parsed.traveler_count
            and parsed.traveler_count > 0
        ):
            cheapest_flight = min(parsed.flight_prices_per_person)
            cheapest_hotel_total = min(parsed.hotel_totals)
            return (cheapest_flight * parsed.traveler_count) + cheapest_hotel_total

        if parsed.destination and parsed.trip_nights and parsed.traveler_count:
            avg_flight = lookup_avg_price_tool.func(parsed.destination, "flight")
            avg_hotel = lookup_avg_price_tool.func(parsed.destination, "hotel_midrange")

            flight_component = float(avg_flight.get("avg_price", 0.0)) * parsed.traveler_count
            hotel_component = float(avg_hotel.get("avg_price", 0.0)) * parsed.trip_nights
            return flight_component + hotel_component

        return 0.0

    def _run_analysis_task(self) -> str:
        budget_analysis_agent = Agent(
            role="Travel Budget Analyst",
            goal=(
                "Assess current plan cost against target budget, benchmark against "
                "destination pricing, and identify biggest savings opportunities."
            ),
            backstory=(
                "You are a forensic travel budget analyst. You quantify overspend and "
                "return practical savings recommendations."
            ),
            tools=[lookup_avg_price_tool, get_budget_tiers_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        analysis_task = Task(
            name="analyze_budget_task",
            description=(
                "Analyze this plan against budget using tool calls as needed.\n"
                f"Destination: {self.state.destination}\n"
                f"Current Estimated Total: ${self.state.current_cost:.2f}\n"
                f"Target Budget: ${self.state.target_budget:.2f}\n"
                f"Travelers: {self.state.traveler_count}\n"
                f"Trip Nights: {self.state.trip_nights}\n"
                f"Current Plan:\n{self.state.current_plan}\n"
                "Return a Budget Gap Analysis with explicit savings opportunities."
            ),
            expected_output=(
                "Budget Gap Analysis including current total, target budget, gap, "
                "benchmark references, and top cost-reduction actions."
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
                "Apply concrete changes to reduce cost while preserving trip quality, "
                "and always output an updated estimated total."
            ),
            backstory=(
                "You are a tactical optimizer. You convert budget analysis into specific "
                "plan swaps with clear savings math."
            ),
            tools=[lookup_avg_price_tool],
            llm=self.llm_model,
            verbose=self.verbose,
        )

        adjustment_task = Task(
            name="adjust_plan_task",
            description=(
                "Using the budget analysis below, apply 1-2 concrete adjustments.\n"
                f"Destination: {self.state.destination}\n"
                f"Current Estimated Total: ${self.state.current_cost:.2f}\n"
                f"Target Budget: ${self.state.target_budget:.2f}\n"
                f"Travelers: {self.state.traveler_count}\n"
                f"Trip Nights: {self.state.trip_nights}\n"
                f"Budget Analysis:\n{analysis_output}\n"
                "Return the updated plan and include this exact final line format:\n"
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
