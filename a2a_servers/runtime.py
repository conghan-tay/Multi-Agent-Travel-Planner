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
from crewai.tools import tool
from dotenv import load_dotenv

SPECIALIST_TOOL_NAME = "run_specialist"
AGENT_CARD_PATH = "/.well-known/agent-card.json"
JSONRPC_PATH = "/a2a"
SpecialistRunner = Callable[[str], Awaitable[str]]
logger = logging.getLogger(__name__)


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


def _format_runner_error(exc: Exception) -> str:
    return f"Specialist execution failed. {type(exc).__name__}: {exc}"


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
