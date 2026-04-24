"""CLI entrypoint: python -m agents.orchestrator '<travel request>'."""

from __future__ import annotations

import argparse
import sys

from .crew import TravelOrchestratorCrew


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m agents.orchestrator",
        description="Run Step-6 TravelOrchestratorCrew via A2A specialist delegation.",
    )
    parser.add_argument("request", help="Natural-language travel request.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable CrewAI verbose trace for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = TravelOrchestratorCrew(verbose=args.verbose).run(args.request)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
