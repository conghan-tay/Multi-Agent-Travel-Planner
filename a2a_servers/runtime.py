"""Shared runtime for exposing specialist crews as A2A JSON-RPC servers."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import threading
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Callable

from a2a.server.agent_execution import AgentExecutor as A2AAgentExecutor
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentSkill
from crewai import Agent
from crewai.a2a.config import A2AServerConfig
from crewai.a2a.utils.task import cancel as cancel_task
from crewai.a2a.utils.task import execute as execute_task
from crewai.hooks import register_before_tool_call_hook
from crewai.hooks.tool_hooks import ToolCallHookContext
from crewai.tools import tool
from dotenv import load_dotenv

from guards.cooldown_guard import CooldownGuard

SPECIALIST_TOOL_NAME = "run_specialist"
AGENT_CARD_PATH = "/.well-known/agent-card.json"
JSONRPC_PATH = "/a2a"
COOLDOWN_SENTINEL_PREFIX = "__crew_mas_cooldown_blocked__:"
SpecialistRunner = Callable[[str], Awaitable[str]]
logger = logging.getLogger(__name__)
_cooldown_guard = CooldownGuard()
_cooldown_hook_registered = False
_cooldown_hook_lock = threading.Lock()
_adapter_tool_specialists: dict[int, str] = {}


@dataclass(frozen=True)
class SpecialistServerSpec:
    """Configuration contract for one specialist A2A server."""

    specialist_id: str
    display_name: str
    description: str
    port: int
    skills: list[AgentSkill]


def _resolve_adapter_model() -> str:
    """Resolve a model name for the adapter agent."""
    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if llm_provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _resolve_cooldown_seconds() -> int:
    raw_value = os.getenv("COOLDOWN_SECONDS", "60").strip()
    try:
        cooldown_seconds = int(raw_value)
    except ValueError:
        logger.warning("Invalid COOLDOWN_SECONDS=%r. Falling back to 60.", raw_value)
        return 60
    return max(cooldown_seconds, 0)


def _format_runner_error(exc: Exception) -> str:
    return f"Specialist execution failed. {type(exc).__name__}: {exc}"


def _format_cooldown_message(specialist_id: str, remaining_seconds: int) -> str:
    return (
        f"Cooldown active for {specialist_id}. "
        f"Try again in {remaining_seconds} seconds."
    )


def _build_cooldown_sentinel(message: str) -> str:
    return f"{COOLDOWN_SENTINEL_PREFIX}{message}"


def _extract_cooldown_sentinel(user_request: str) -> str | None:
    if user_request.startswith(COOLDOWN_SENTINEL_PREFIX):
        return user_request.removeprefix(COOLDOWN_SENTINEL_PREFIX)
    return None


def _before_adapter_tool_call(context: ToolCallHookContext) -> bool | None:
    """Apply cooldown only to registered A2A adapter tools."""
    if context.tool_name != SPECIALIST_TOOL_NAME:
        return None

    specialist_id = _adapter_tool_specialists.get(id(context.tool))
    if specialist_id is None:
        return None

    _cooldown_guard.cooldown_seconds = _resolve_cooldown_seconds()
    decision = _cooldown_guard.check_and_mark(specialist_id)
    if decision.allowed:
        return None

    message = _format_cooldown_message(
        specialist_id=specialist_id,
        remaining_seconds=decision.remaining_seconds,
    )
    context.tool_input["user_request"] = _build_cooldown_sentinel(message)
    return None


def _ensure_cooldown_hook_registered() -> None:
    global _cooldown_hook_registered

    if _cooldown_hook_registered:
        return

    with _cooldown_hook_lock:
        if _cooldown_hook_registered:
            return
        register_before_tool_call_hook(_before_adapter_tool_call)
        _cooldown_hook_registered = True


def _register_adapter_cooldown_tool(tool_instance, specialist_id: str) -> None:
    _ensure_cooldown_hook_registered()
    _adapter_tool_specialists[id(tool_instance)] = specialist_id


def reset_cooldown_state_for_tests() -> None:
    """Reset adapter cooldown state without unregistering the process-wide hook."""
    _cooldown_guard.reset()
    _adapter_tool_specialists.clear()


def _run_async_runner(runner: SpecialistRunner, user_request: str) -> str:
    """Run an async specialist runner from CrewAI's synchronous tool call path."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(runner(user_request))

    result: str | None = None
    error: BaseException | None = None

    def worker() -> None:
        nonlocal result, error
        try:
            result = asyncio.run(runner(user_request))
        except BaseException as exc:  # noqa: BLE001
            error = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()

    if error is not None:
        raise error
    if result is None:
        raise RuntimeError("Specialist runner completed without returning a result")
    return result


def _build_run_specialist_tool(runner: SpecialistRunner):
    @tool(SPECIALIST_TOOL_NAME)
    def run_specialist(user_request: str) -> str:
        """Execute the wrapped specialist crew for one user request."""
        cooldown_message = _extract_cooldown_sentinel(user_request)
        if cooldown_message is not None:
            return cooldown_message

        try:
            return _run_async_runner(runner, user_request)
        except Exception as exc:
            logger.exception(
                "Specialist runner failed for request=%r: %s",
                user_request,
                exc,
            )
            return _format_runner_error(exc)

    return run_specialist


def build_adapter_agent(
    spec: SpecialistServerSpec,
    runner: SpecialistRunner,
) -> Agent:
    """Create an adapter agent with A2A server metadata."""
    run_specialist_tool = _build_run_specialist_tool(runner)
    _register_adapter_cooldown_tool(run_specialist_tool, spec.specialist_id)
    server_config = A2AServerConfig(
        name=spec.specialist_id,
        description=spec.description,
        skills=spec.skills,
    )
    return Agent(
        role=f"{spec.display_name} Adapter",
        goal=(
            "Handle one delegated user request by calling run_specialist exactly once "
            "and return only the specialist response."
        ),
        backstory=(
            "You are a protocol adapter between A2A clients and an internal specialist. "
            "You do not solve tasks yourself."
        ),
        tools=[run_specialist_tool],
        llm=_resolve_adapter_model(),
        verbose=False,
        a2a=server_config,
    )


class CrewAIA2AExecutorBridge(A2AAgentExecutor):
    """a2a-sdk executor bridge backed by CrewAI A2A task utilities."""

    def __init__(self, adapter_agent: Agent):
        self._adapter_agent = adapter_agent

    async def execute(self, context, event_queue: EventQueue) -> None:
        await execute_task(self._adapter_agent, context, event_queue)

    async def cancel(self, context, event_queue: EventQueue) -> None:
        await cancel_task(context, event_queue)


def build_app(
    spec: SpecialistServerSpec,
    runner: SpecialistRunner,
    host: str = "127.0.0.1",
    port: int | None = None,
):
    """Build a FastAPI app exposing A2A JSON-RPC and Agent Card endpoints."""
    from a2a.server.apps.jsonrpc import A2AFastAPIApplication

    adapter_agent = build_adapter_agent(spec=spec, runner=runner)
    effective_port = port or spec.port
    base_url = f"http://{host}:{effective_port}"
    agent_card = adapter_agent.to_agent_card(base_url).model_copy(
        update={"url": f"{base_url}{JSONRPC_PATH}"}
    )

    request_handler = DefaultRequestHandler(
        agent_executor=CrewAIA2AExecutorBridge(adapter_agent),
        task_store=InMemoryTaskStore(),
    )

    return A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    ).build(
        agent_card_url=AGENT_CARD_PATH,
        rpc_url=JSONRPC_PATH,
        title=f"{spec.specialist_id} A2A Server",
    )


def build_parser(program_name: str, default_port: int) -> argparse.ArgumentParser:
    """Build a common CLI parser for specialist A2A servers."""
    parser = argparse.ArgumentParser(prog=program_name)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--log-level", default="info")
    return parser


def run_server(app, host: str, port: int, log_level: str) -> None:
    """Run a FastAPI app under uvicorn."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level=log_level)


def run_specialist_server(
    spec: SpecialistServerSpec,
    runner: SpecialistRunner,
    argv: list[str] | None = None,
    program_name: str | None = None,
) -> None:
    """CLI entrypoint implementation for one specialist."""
    load_dotenv(override=True)
    parser = build_parser(
        program_name=program_name or f"python -m a2a_servers.{spec.specialist_id}_server",
        default_port=spec.port,
    )
    args = parser.parse_args(argv)
    app = build_app(spec=spec, runner=runner, host=args.host, port=args.port)
    run_server(app=app, host=args.host, port=args.port, log_level=args.log_level)
