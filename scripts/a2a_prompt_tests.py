"""A2A prompt test harness for itinerary/scout/budget specialist servers."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_TARGET = "all"

PROMPT_ITINERARY = "Plan a 5-day trip to Paris in October for 2 people"
PROMPT_SCOUT = (
    "Find flights and hotels from NYC to Tokyo for Oct 1 to Oct 8 for 2 travelers"
)
PROMPT_BUDGET = (
    "Optimize this package under $3000. Route: NYC to Tokyo. Flight: $900 per traveler. "
    "Hotel: $1400 total. Dates: 2026-10-01 to 2026-10-08 for 2 travelers."
)


@dataclass(frozen=True)
class TargetConfig:
    name: str
    endpoint: str
    prompt: str
    server_log: str


TARGETS: dict[str, TargetConfig] = {
    "itinerary": TargetConfig(
        name="itinerary",
        endpoint="http://127.0.0.1:9001/a2a",
        prompt=PROMPT_ITINERARY,
        server_log="logs/itinerary-a2a.log",
    ),
    "scout": TargetConfig(
        name="scout",
        endpoint="http://127.0.0.1:9002/a2a",
        prompt=PROMPT_SCOUT,
        server_log="logs/scout-a2a.log",
    ),
    "budget": TargetConfig(
        name="budget",
        endpoint="http://127.0.0.1:9003/a2a",
        prompt=PROMPT_BUDGET,
        server_log="logs/budget-a2a.log",
    ),
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.a2a_prompt_tests",
        description="Send fixed prompts to one or all A2A specialist servers.",
    )
    parser.add_argument(
        "--target",
        choices=["itinerary", "scout", "budget", "all"],
        default=DEFAULT_TARGET,
        help="Which specialist to test. Use 'all' to run all three sequentially.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Write verbose debug logs and server log snapshots.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional deterministic run id for output folder naming.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds for each request.",
    )
    return parser.parse_args(argv)


def _resolve_run_dir(run_id: str) -> Path:
    if run_id.strip():
        resolved = run_id.strip()
    else:
        resolved = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path("logs") / "a2a_test_runs" / resolved
    path.mkdir(parents=True, exist_ok=True)
    return path


def _selected_targets(target: str) -> list[TargetConfig]:
    if target == "all":
        return [TARGETS["itinerary"], TARGETS["scout"], TARGETS["budget"]]
    return [TARGETS[target]]


def _build_payload(prompt: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": prompt,
                    }
                ],
            }
        },
    }


def _collect_text_values(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        if node.get("kind") == "text" and isinstance(node.get("text"), str):
            found.append(node["text"])
        for value in node.values():
            found.extend(_collect_text_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_text_values(item))
    return found


def _tail_file(path: Path, max_lines: int = 400) -> str:
    if not path.exists():
        return f"[missing] {path}\n"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-max_lines:]
    return "\n".join(tail) + ("\n" if tail else "")


def _send_jsonrpc(
    endpoint: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()

    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - started) * 1000
            return {
                "ok_http": 200 <= resp.status < 300,
                "status_code": resp.status,
                "headers": dict(resp.headers.items()),
                "raw_text": raw,
                "elapsed_ms": round(elapsed_ms, 2),
                "transport_error": "",
            }
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "ok_http": False,
            "status_code": exc.code,
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "raw_text": raw,
            "elapsed_ms": round(elapsed_ms, 2),
            "transport_error": f"HTTPError: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "ok_http": False,
            "status_code": 0,
            "headers": {},
            "raw_text": "",
            "elapsed_ms": round(elapsed_ms, 2),
            "transport_error": f"{type(exc).__name__}: {exc}",
        }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_target(
    target: TargetConfig,
    run_dir: Path,
    timeout_seconds: int,
    verbose: bool,
) -> dict[str, Any]:
    request_payload = _build_payload(target.prompt)
    request_path = run_dir / f"request.{target.name}.json"
    response_path = run_dir / f"response.{target.name}.json"
    summary_path = run_dir / f"summary.{target.name}.txt"

    _write_json(request_path, request_payload)
    response_meta = _send_jsonrpc(target.endpoint, request_payload, timeout_seconds)

    parsed_json: dict[str, Any] | None = None
    parse_error = ""
    if response_meta["raw_text"]:
        try:
            maybe_json = json.loads(response_meta["raw_text"])
            if isinstance(maybe_json, dict):
                parsed_json = maybe_json
        except json.JSONDecodeError as exc:
            parse_error = f"JSONDecodeError: {exc}"

    jsonrpc_error = ""
    task_id = ""
    extracted_text = ""
    ok = bool(response_meta["ok_http"])

    if parsed_json is not None:
        if isinstance(parsed_json.get("error"), dict):
            jsonrpc_error = str(parsed_json["error"])
            ok = False

        result = parsed_json.get("result")
        if isinstance(result, dict):
            maybe_id = result.get("id") or result.get("taskId")
            if isinstance(maybe_id, str):
                task_id = maybe_id

        text_values = _collect_text_values(parsed_json)
        if text_values:
            extracted_text = "\n\n".join(text_values)
    else:
        if response_meta["ok_http"]:
            ok = False

    if parse_error:
        ok = False
    if response_meta["transport_error"]:
        ok = False

    response_record = {
        "status": "ok" if ok else "failed",
        "target": target.name,
        "endpoint": target.endpoint,
        "status_code": response_meta["status_code"],
        "elapsed_ms": response_meta["elapsed_ms"],
        "headers": response_meta["headers"],
        "transport_error": response_meta["transport_error"],
        "json_decode_error": parse_error,
        "jsonrpc_error": jsonrpc_error,
        "task_id": task_id,
        "extracted_text": extracted_text,
        "raw_response_text": response_meta["raw_text"],
        "parsed_response": parsed_json,
    }
    _write_json(response_path, response_record)

    summary_lines = [
        f"target={target.name}",
        f"endpoint={target.endpoint}",
        f"status={'ok' if ok else 'failed'}",
        f"status_code={response_meta['status_code']}",
        f"elapsed_ms={response_meta['elapsed_ms']}",
        f"task_id={task_id or '(none)'}",
    ]
    if response_meta["transport_error"]:
        summary_lines.append(f"transport_error={response_meta['transport_error']}")
    if parse_error:
        summary_lines.append(f"json_decode_error={parse_error}")
    if jsonrpc_error:
        summary_lines.append(f"jsonrpc_error={jsonrpc_error}")
    if extracted_text:
        summary_lines.append("\n--- extracted_text ---\n")
        summary_lines.append(extracted_text)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    if verbose:
        debug_path = run_dir / f"debug.{target.name}.log"
        debug_lines = [
            f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
            f"endpoint={target.endpoint}",
            "request_headers={'Content-Type': 'application/json'}",
            f"request_payload={json.dumps(request_payload, ensure_ascii=True)}",
            f"http_status={response_meta['status_code']}",
            f"elapsed_ms={response_meta['elapsed_ms']}",
            f"response_headers={json.dumps(response_meta['headers'], ensure_ascii=True)}",
            f"transport_error={response_meta['transport_error'] or '(none)'}",
            f"json_decode_error={parse_error or '(none)'}",
            f"jsonrpc_error={jsonrpc_error or '(none)'}",
            "",
            "--- raw_response_text ---",
            response_meta["raw_text"] or "(empty)",
        ]
        debug_path.write_text("\n".join(debug_lines) + "\n", encoding="utf-8")

        snapshot_path = run_dir / f"serverlog.{target.name}.snapshot.log"
        snapshot_path.write_text(
            _tail_file(Path(target.server_log)),
            encoding="utf-8",
        )

    return {
        "target": target.name,
        "status": "ok" if ok else "failed",
        "status_code": response_meta["status_code"],
        "elapsed_ms": response_meta["elapsed_ms"],
        "task_id": task_id,
        "request_file": request_path.name,
        "response_file": response_path.name,
        "summary_file": summary_path.name,
    }


def _write_run_summary(run_dir: Path, results: list[dict[str, Any]], args: argparse.Namespace) -> None:
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_dir.name,
        "target": args.target,
        "verbose": bool(args.verbose),
        "timeout_seconds": int(args.timeout),
        "results": results,
    }
    _write_json(run_dir / "manifest.json", manifest)

    lines = [
        "# A2A Prompt Test Run",
        "",
        f"- run_id: `{run_dir.name}`",
        f"- target: `{args.target}`",
        f"- verbose: `{bool(args.verbose)}`",
        f"- timeout_seconds: `{int(args.timeout)}`",
        "",
        "| target | status | http_status | elapsed_ms | task_id |",
        "|---|---|---:|---:|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['target']} | {item['status']} | {item['status_code']} | "
            f"{item['elapsed_ms']} | {item['task_id'] or ''} |"
        )

    (run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    run_dir = _resolve_run_dir(args.run_id)
    targets = _selected_targets(args.target)

    results: list[dict[str, Any]] = []
    for cfg in targets:
        results.append(
            _run_target(
                target=cfg,
                run_dir=run_dir,
                timeout_seconds=args.timeout,
                verbose=args.verbose,
            )
        )

    _write_run_summary(run_dir, results, args)
    has_failure = any(item["status"] != "ok" for item in results)

    print(f"A2A prompt test artifacts: {run_dir}")
    for item in results:
        print(
            f"- {item['target']}: {item['status']} "
            f"(http={item['status_code']}, elapsed_ms={item['elapsed_ms']})"
        )

    return 1 if has_failure else 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

