"""Reusable in-memory cooldown guard for specialist invocations."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CooldownDecision:
    """Result of a cooldown check."""

    allowed: bool
    remaining_seconds: int = 0


class CooldownGuard:
    """Thread-safe per-key cooldown guard backed by in-memory timestamps."""

    def __init__(self, cooldown_seconds: int = 60):
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be greater than or equal to 0")
        self.cooldown_seconds = cooldown_seconds
        self._last_invoked_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def check_and_mark(self, key: str, now: float | None = None) -> CooldownDecision:
        """Allow and mark a key, or block it if still cooling down."""
        if not key:
            raise ValueError("key is required")

        effective_now = time.monotonic() if now is None else now
        with self._lock:
            last_invoked_at = self._last_invoked_at.get(key)
            if last_invoked_at is not None:
                elapsed = effective_now - last_invoked_at
                remaining = self.cooldown_seconds - elapsed
                if remaining > 0:
                    return CooldownDecision(
                        allowed=False,
                        remaining_seconds=max(1, math.ceil(remaining)),
                    )

            self._last_invoked_at[key] = effective_now
            return CooldownDecision(allowed=True)

    def reset(self) -> None:
        """Clear all tracked cooldown state."""
        with self._lock:
            self._last_invoked_at.clear()
