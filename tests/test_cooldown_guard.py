from __future__ import annotations

import pytest

from guards.cooldown_guard import CooldownGuard


def test_cooldown_guard_allows_first_call_and_blocks_second():
    guard = CooldownGuard(cooldown_seconds=60)

    first = guard.check_and_mark("budget_specialist", now=100.0)
    second = guard.check_and_mark("budget_specialist", now=110.0)

    assert first.allowed is True
    assert second.allowed is False
    assert second.remaining_seconds == 50


def test_cooldown_guard_allows_call_after_window_expires():
    guard = CooldownGuard(cooldown_seconds=60)

    guard.check_and_mark("budget_specialist", now=100.0)
    decision = guard.check_and_mark("budget_specialist", now=160.0)

    assert decision.allowed is True


def test_cooldown_guard_tracks_keys_independently():
    guard = CooldownGuard(cooldown_seconds=60)

    guard.check_and_mark("itinerary_specialist", now=100.0)
    decision = guard.check_and_mark("budget_specialist", now=110.0)

    assert decision.allowed is True


def test_cooldown_guard_rejects_negative_cooldown():
    with pytest.raises(ValueError, match="cooldown_seconds"):
        CooldownGuard(cooldown_seconds=-1)
