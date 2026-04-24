#!/usr/bin/env python3
"""
Extract the Must-Fix Items section from a Claude code review report.
Usage: python3 scripts/extract_must_fix.py <report_file>
Exits 0 with content printed to stdout if must-fix items are found.
Exits 0 with no output if section is missing (not an error).
Exits 1 if the file cannot be read.
"""

import sys
import pathlib


def extract_must_fix(content: str) -> str:
    start = content.find("🔴 Must-Fix Items")
    end = content.find("🟡 Recommended Refactors")

    if start == -1 or end == -1:
        return ""

    section = content[start:end]
    lines = [
        line for line in section.splitlines()
        if "🔴 Must-Fix Items" not in line and line.strip()
    ]
    return "\n".join(lines)


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

    result = extract_must_fix(content)
    if result:
        print(result)


if __name__ == "__main__":
    main()