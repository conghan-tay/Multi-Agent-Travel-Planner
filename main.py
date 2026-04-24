"""Root CLI for the Step-6 travel orchestrator."""

from __future__ import annotations

import argparse
import sys

from agents.orchestrator import TravelOrchestratorCrew


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Run the TravelOrchestratorCrew A2A client.",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Natural-language travel request. If omitted, starts interactive mode.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable CrewAI verbose trace for debugging.",
    )
    return parser.parse_args(argv)


def _run_once(user_request: str, verbose: bool) -> str:
    return TravelOrchestratorCrew(verbose=verbose).run(user_request)


def _run_repl(verbose: bool) -> int:
    print("Travel Orchestrator ready. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            user_request = input("> ").strip()
        except EOFError:
            print()
            return 0

        if not user_request:
            continue
        if user_request.lower() in {"exit", "quit"}:
            return 0

        try:
            print(_run_once(user_request, verbose=verbose))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.request:
        try:
            print(_run_once(args.request, verbose=args.verbose))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    return _run_repl(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
