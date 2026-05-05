# Tech Debt: Async Tool Execution in A2A Specialist Adapters

## Summary

The orchestrator correctly routed flight and hotel requests to `flight_hotel_specialist`, but the scout A2A server returned generic failure text instead of a travel package summary. The failure was caused by a mismatch between Python async execution, CrewAI tool invocation, and the way CrewAI 1.12 runs A2A adapter tools.

This note documents the problem, the solutions tried, and the final CrewAI 1.12-compatible fix.

## Problem Narrative

The failing command was:

```bash
python main.py 'Find flights and hotels from NYC to Tokyo for Oct 1 to Oct 8 for 2 travelers' --verbose
```

The verbose trace showed that the orchestrator selected the correct remote agent:

```text
flight_hotel_specialist
```

So the issue was not orchestrator routing. The A2A delegation reached the scout server, but the remote response degraded into generic support-style failure messages such as:

```text
I am unable to provide a completed response.
```

and later:

```text
I'm currently unable to find flights and hotels due to a technical issue.
```

The useful signal was in `logs/scout-a2a.log`, which showed:

```text
asyncio.run() cannot be called from a running event loop
```

and warnings like:

```text
coroutine ... was never awaited
```

Those log lines showed that the A2A server was not failing at the HTTP layer. It was failing while trying to execute the scout specialist from inside the adapter tool.

## Root Cause

`FlightHotelScoutCrew` has an async workflow because the flight and hotel searches run concurrently:

```python
async def run_async(self, user_request: str) -> str:
    result = await self.crew.kickoff_async(inputs={"user_request": user_request})
    return str(result)
```

The direct CLI wrapper used:

```python
def run(self, user_request: str) -> str:
    return asyncio.run(self.run_async(user_request))
```

That is valid from a plain CLI process because no event loop is running yet. `asyncio.run(...)` creates a new event loop, runs the coroutine, and closes the loop.

It is not valid inside the A2A server path. The A2A server runs under Uvicorn/FastAPI, which already has an active event loop handling the HTTP request. Calling `asyncio.run(...)` from inside that active loop raises:

```text
asyncio.run() cannot be called from a running event loop
```

The confusing part was CrewAI tool execution. We expected that an async CrewAI tool would be awaited in the A2A path. In CrewAI 1.12, the real A2A adapter path invoked the tool through its synchronous `run()` path. That meant an async tool alone still ended up trying to bridge async work through sync tool execution.

In short:

```text
A2A/FastAPI request is async
CrewAI 1.12 adapter invokes tool sync run()
Scout specialist is async
asyncio.run(...) inside the active server event loop fails
```

## Solutions Tried

### 1. Direct Async Scout Runner

The first improvement was to make the scout A2A wrapper use the native async path:

```python
async def run_scout_specialist(user_request: str) -> str:
    return await FlightHotelScoutCrew(verbose=False).run_async(user_request)
```

This was correct, but it did not fully solve the problem because the shared adapter tool was still synchronous.

### 2. Async CrewAI Adapter Tool

The next attempt was to make `run_specialist` an async CrewAI tool:

```python
@tool("run_specialist")
async def run_specialist(user_request: str) -> str:
    return await runner(user_request)
```

This matched CrewAI documentation for async tools and would be the cleanest model if the A2A adapter awaited the tool through the async tool path.

However, in the installed CrewAI version (`1.12.2`), the live A2A adapter path still invoked the tool through sync `run()`. The result was the same event-loop failure, now pointing at the async `run_specialist` coroutine.

### 3. Diagnostics

We added explicit logging around specialist runner failures so real exceptions are visible in server logs:

```python
logger.exception(
    "Specialist runner failed for request=%r: %s",
    user_request,
    exc,
)
```

The adapter also returns a visible failure string:

```python
Specialist execution failed. RuntimeError: ...
```

This is useful for local learning and debugging because CrewAI may otherwise collapse the actual exception into a generic support message.

## Final Solution

The final fix keeps the specialist runner contract async, but adapts it to CrewAI 1.12's synchronous tool invocation behavior.

### Specialist Runners Are Async

Scout uses the actual async crew method:

```python
async def run_scout_specialist(user_request: str) -> str:
    return await FlightHotelScoutCrew(verbose=False).run_async(user_request)
```

Itinerary and budget remain internally synchronous, so their A2A runners use `asyncio.to_thread(...)`:

```python
async def run_itinerary_specialist(user_request: str) -> str:
    return await asyncio.to_thread(
        lambda: ItineraryBuilderCrew(verbose=False).run(user_request)
    )
```

```python
async def run_budget_specialist(user_request: str) -> str:
    return await asyncio.to_thread(
        lambda: BudgetOptimizerCrew(verbose=False).run(user_request)
    )
```

This keeps the A2A-facing contract consistent:

```python
SpecialistRunner = Callable[[str], Awaitable[str]]
```

### Adapter Tool Stays Sync

Because CrewAI 1.12 invokes the adapter tool through sync `run()`, `run_specialist` remains a synchronous tool:

```python
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
```

The important bridge is `_run_async_runner(...)`:

```python
def _run_async_runner(runner: SpecialistRunner, user_request: str) -> str:
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
        except BaseException as exc:
            error = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()

    if error is not None:
        raise error
    if result is None:
        raise RuntimeError("Specialist runner completed without returning a result")
    return result
```

Behavior:

- If no event loop is active, run the async specialist with `asyncio.run(...)`.
- If an event loop is already active, start a dedicated worker thread.
- The worker thread owns its own event loop, so `asyncio.run(...)` is valid there.
- The sync CrewAI tool blocks until the async specialist completes and returns a string.
- Any exception from the worker thread is re-raised and logged by the adapter tool.

## Why The Thread Exists

The thread is not used to make the business logic parallel. It exists to bridge a sync CrewAI tool boundary to an async specialist runner when the current thread already has a running event loop.

Without the thread:

```text
Uvicorn event loop
  -> CrewAI sync tool run()
    -> asyncio.run(async specialist)
    -> RuntimeError: event loop already running
```

With the thread:

```text
Uvicorn event loop
  -> CrewAI sync tool run()
    -> worker thread
      -> asyncio.run(async specialist)
      -> return result
```

This is a compatibility workaround for CrewAI 1.12's A2A tool execution path.

## Files To Know

- `a2a_servers/runtime.py`
  - Defines the shared A2A adapter runtime.
  - Contains `SpecialistRunner`, `_run_async_runner(...)`, and `run_specialist`.
- `a2a_servers/scout_server.py`
  - Uses `FlightHotelScoutCrew.run_async(...)` directly.
- `a2a_servers/itinerary_server.py`
  - Wraps the synchronous itinerary crew with `asyncio.to_thread(...)`.
- `a2a_servers/budget_server.py`
  - Wraps the synchronous budget crew with `asyncio.to_thread(...)`.
- `tests/test_a2a_servers.py`
  - Contains regression coverage for the sync tool path, active event loop case, A2A TestClient path, and exception diagnostics.

## Regression Tests

The tests cover the important failure modes:

- Sync tool path can run an async runner.
- Sync tool path also works when called while an event loop is already active.
- A2A TestClient path returns async runner output.
- Runner exceptions are logged and surfaced as visible failure text.

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected result:

```text
all tests pass
```

## Manual Retest

After changing A2A runtime code, restart the servers. Existing background processes will keep running old code until restarted.

```bash
make stop
make start-tools
make start-agents
python main.py 'Find flights and hotels from NYC to Tokyo for Oct 1 to Oct 8 for 2 travelers' --verbose
```

Expected behavior:

- Orchestrator routes to `flight_hotel_specialist`.
- Scout A2A server runs the flight and hotel searches.
- Response contains a travel options summary instead of generic technical failure text.

## Future Cleanup

This bridge should be revisited when upgrading CrewAI. If a newer CrewAI A2A execution path reliably awaits async tools via `tool.arun(...)`, the sync thread bridge may no longer be necessary.

Before removing it, keep or adapt the regression tests that prove:

- A2A adapter can execute an async specialist runner.
- No `asyncio.run() cannot be called from a running event loop` error occurs.
- Real runner exceptions remain visible in logs.
