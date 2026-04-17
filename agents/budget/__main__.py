"""CLI entrypoint: python -m agents.budget '<budget optimization request>'."""

from __future__ import annotations

import argparse
import sys

from .crew import BudgetOptimizerCrew


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m agents.budget",
        description="Run Step-4 BudgetOptimizerCrew directly (no A2A/orchestrator).",
    )
    parser.add_argument("request", help="Natural-language budget optimization request.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable CrewAI verbose trace for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = BudgetOptimizerCrew(verbose=args.verbose).run(args.request)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
