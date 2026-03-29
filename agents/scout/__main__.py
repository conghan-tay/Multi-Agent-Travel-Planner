"""CLI entrypoint: python -m agents.scout '<travel request>'."""

from __future__ import annotations

import argparse
import sys

from .crew import FlightHotelScoutCrew


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m agents.scout",
        description="Run Step-3 FlightHotelScoutCrew directly (no A2A/orchestrator).",
    )
    parser.add_argument("request", help="Natural-language flight + hotel request.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable CrewAI verbose trace for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = FlightHotelScoutCrew(verbose=args.verbose).run(args.request)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
