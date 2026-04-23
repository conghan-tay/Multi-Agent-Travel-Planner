"""A2A server wrapper for Step-4 BudgetOptimizerCrew."""

from __future__ import annotations

from a2a.types import AgentSkill
from dotenv import load_dotenv

from agents.budget import BudgetOptimizerCrew

from .runtime import SpecialistServerSpec, build_app, run_specialist_server

SPEC = SpecialistServerSpec(
    specialist_id="budget_specialist",
    display_name="Budget Specialist",
    description=(
        "Optimizes travel packages against a target budget through iterative analysis "
        "and adjustment."
    ),
    port=9003,
    skills=[
        AgentSkill(
            id="optimize_budget",
            name="Optimize Budget",
            description="Iteratively reduce travel package costs toward a target budget.",
            tags=["budget", "optimizer", "loop", "flow"],
        ),
    ],
)


def run_budget_specialist(user_request: str) -> str:
    return BudgetOptimizerCrew(verbose=False).run(user_request)


def make_app():
    load_dotenv(override=True)
    return build_app(spec=SPEC, runner=run_budget_specialist)


def main() -> None:
    run_specialist_server(
        spec=SPEC,
        runner=run_budget_specialist,
        program_name="python -m a2a_servers.budget_server",
    )


if __name__ == "__main__":
    main()
