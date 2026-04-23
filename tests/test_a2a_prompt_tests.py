from __future__ import annotations

import json
from pathlib import Path

from scripts import a2a_prompt_tests as mod


class _DummyResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload
        self.headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_target_all_creates_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(req, timeout=0):
        _ = timeout
        payload = {
            "jsonrpc": "2.0",
            "id": "x",
            "result": {
                "id": "task-123",
                "artifacts": [
                    {"parts": [{"kind": "text", "text": "ok response"}]},
                ],
            },
        }
        return _DummyResponse(200, payload)

    monkeypatch.setattr(mod.request, "urlopen", fake_urlopen)
    exit_code = mod.run(["--target", "all", "--run-id", "testrun"])

    assert exit_code == 0
    run_dir = tmp_path / "logs" / "a2a_test_runs" / "testrun"
    assert run_dir.exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "SUMMARY.md").exists()
    assert (run_dir / "request.itinerary.json").exists()
    assert (run_dir / "response.scout.json").exists()
    assert (run_dir / "summary.budget.txt").exists()


def test_single_target_payload_shape(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured: list[dict] = []

    def fake_urlopen(req, timeout=0):
        captured.append(json.loads(req.data.decode("utf-8")))
        _ = timeout
        return _DummyResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"id": "t"}})

    monkeypatch.setattr(mod.request, "urlopen", fake_urlopen)
    exit_code = mod.run(["--target", "budget", "--run-id", "one"])

    assert exit_code == 0
    assert len(captured) == 1
    payload = captured[0]
    assert payload["jsonrpc"] == "2.0"
    assert payload["method"] == "message/send"
    assert payload["params"]["message"]["role"] == "user"
    assert payload["params"]["message"]["parts"][0]["kind"] == "text"
    assert "Optimize this package under $3000." in payload["params"]["message"]["parts"][0]["text"]


def test_failure_path_returns_non_zero_and_writes_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_urlopen(req, timeout=0):
        _ = req
        _ = timeout
        return _DummyResponse(500, {"jsonrpc": "2.0", "id": "x", "error": {"code": -32000}})

    monkeypatch.setattr(mod.request, "urlopen", fake_urlopen)
    exit_code = mod.run(["--target", "itinerary", "--run-id", "fail"])

    assert exit_code == 1
    run_dir = tmp_path / "logs" / "a2a_test_runs" / "fail"
    response = json.loads((run_dir / "response.itinerary.json").read_text())
    assert response["status"] == "failed"


def test_verbose_writes_debug_and_serverlog_snapshot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "itinerary-a2a.log").write_text("line1\nline2\n", encoding="utf-8")

    def fake_urlopen(req, timeout=0):
        _ = req
        _ = timeout
        return _DummyResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"id": "t"}})

    monkeypatch.setattr(mod.request, "urlopen", fake_urlopen)
    exit_code = mod.run(["--target", "itinerary", "--run-id", "verbose", "--verbose"])

    assert exit_code == 0
    run_dir = tmp_path / "logs" / "a2a_test_runs" / "verbose"
    assert (run_dir / "debug.itinerary.log").exists()
    assert (run_dir / "serverlog.itinerary.snapshot.log").exists()

