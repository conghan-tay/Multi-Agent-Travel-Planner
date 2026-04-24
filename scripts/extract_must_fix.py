#!/usr/bin/env python3
"""
Read a Claude code review report and extract the Final Verdict section.
Prints the section to stdout when the verdict is NOT READY TO MERGE (signals
the PR should be blocked). Prints nothing when the verdict is READY TO MERGE.
Usage: python3 scripts/extract_must_fix.py <report_file>
Exits 0 in both cases. Exits 1 if the file cannot be read.
"""

import sys
import pathlib

NOT_READY_TOKEN = "VERDICT: NOT READY TO MERGE"


def extract_verdict(content: str) -> str:
    if NOT_READY_TOKEN not in content:
        return ""

    start = content.find("⚖️ Final Verdict")
    if start == -1:
        return NOT_READY_TOKEN

    return content[start:].strip()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: extract_must_fix.py <report_file>", file=sys.stderr)
        sys.exit(1)

    report_path = pathlib.Path(sys.argv[1])

    try:
        content = report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: file not found: {report_path}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    result = extract_verdict(content)
    if result:
        print(result)


if __name__ == "__main__":
    main()
