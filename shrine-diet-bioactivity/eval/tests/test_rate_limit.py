"""Unit tests for eval.llm_clients.rate_limit.

All tests use injected fake clocks and sleep functions so no real sleeping occurs.
The global monkeypatch is installed / uninstalled around tests that exercise
``install_global_rate_limit`` to prevent patch leakage into other test modules.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fake_clock(start: float = 0.0):  # type: ignore[return]
    """Return (clock, sleep, state_dict).

    clock() returns state['now'].
    sleep(s) advances state['now'] by s.
    state['now'] can be read or set directly in tests.
    """
    t: dict[str, float] = {"now": start}

    def clock() -> float:
        return t["now"]

    def sleep(s: float) -> None:
        t["now"] += s

    return clock, sleep, t


# ---------------------------------------------------------------------------
# Import under test (lazy so that any ImportError surfaces as test failure)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def rate_limit_module():  # type: ignore[return]
    """Import and return the rate_limit module.

    Using autouse=False so tests can import it once and assert on module state.
    """
    from eval.llm_clients import rate_limit  # type: ignore[import-not-found]
    return rate_limit


@pytest.fixture(autouse=True)
def ensure_uninstalled():  # type: ignore[return]
    """Teardown: always uninstall the global patch after each test so it
    doesn't leak into sibling test modules and incur real pacing delays."""
    yield
    try:
        from eval.llm_clients.rate_limit import uninstall_global_rate_limit  # type: ignore[import-not-found]
        uninstall_global_rate_limit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: burst up to min cap without sleeping
# ---------------------------------------------------------------------------


def test_limiter_allows_burst_up_to_min_cap() -> None:
    """With max_per_min=5, safety_factor=1.0, 5 acquires must not sleep;
    the 6th must trigger a sleep call."""
    from eval.llm_clients.rate_limit import SlidingWindowRateLimiter  # type: ignore[import-not-found]

    clock, sleep, state = make_fake_clock(0.0)
    sleep_calls: list[float] = []

    def tracking_sleep(s: float) -> None:
        sleep_calls.append(s)
        state["now"] += s

    limiter = SlidingWindowRateLimiter(
        max_per_min=5,
        max_per_hour=200,
        clock=clock,
        sleep=tracking_sleep,
        safety_factor=1.0,
    )

    for _ in range(5):
        limiter.acquire()

    assert sleep_calls == [], "First 5 acquires should not sleep"

    limiter.acquire()
    assert len(sleep_calls) == 1, "6th acquire should have slept once"
    assert sleep_calls[0] > 0


# ---------------------------------------------------------------------------
# Test 2: pacing to hour cap
# ---------------------------------------------------------------------------


def test_limiter_paces_to_hour_cap() -> None:
    """With max_per_hour=3 (safety_factor=1.0), the 4th acquire must sleep
    approximately 3600 - elapsed seconds."""
    from eval.llm_clients.rate_limit import SlidingWindowRateLimiter  # type: ignore[import-not-found]

    clock, sleep, state = make_fake_clock(0.0)
    sleep_calls: list[float] = []

    def tracking_sleep(s: float) -> None:
        sleep_calls.append(s)
        state["now"] += s

    limiter = SlidingWindowRateLimiter(
        max_per_min=100,  # minute cap not binding
        max_per_hour=3,
        clock=clock,
        sleep=tracking_sleep,
        safety_factor=1.0,
    )

    limiter.acquire()
    state["now"] += 1.0
    limiter.acquire()
    state["now"] += 1.0
    limiter.acquire()
    state["now"] += 1.0

    # 4th acquire — hourly cap hit
    limiter.acquire()
    assert len(sleep_calls) == 1
    # Wait should be close to 3600 - elapsed (3s) = ~3597, plus epsilon 0.05
    expected_lower = 3597.0
    expected_upper = 3598.0
    assert expected_lower <= sleep_calls[0] <= expected_upper, (
        f"Expected sleep ~3597s, got {sleep_calls[0]}"
    )


# ---------------------------------------------------------------------------
# Test 3: old grants pruned after 3600s
# ---------------------------------------------------------------------------


def test_limiter_prunes_old_grants() -> None:
    """After the clock advances past 3600s, old grants are pruned and no
    longer count toward the hour window."""
    from eval.llm_clients.rate_limit import SlidingWindowRateLimiter  # type: ignore[import-not-found]

    clock, sleep, state = make_fake_clock(0.0)
    sleep_calls: list[float] = []

    def tracking_sleep(s: float) -> None:
        sleep_calls.append(s)
        state["now"] += s

    limiter = SlidingWindowRateLimiter(
        max_per_min=100,
        max_per_hour=3,
        clock=clock,
        sleep=tracking_sleep,
        safety_factor=1.0,
    )

    # Fill the hour window
    for _ in range(3):
        limiter.acquire()

    # Advance clock by more than 3600s — old grants should be pruned
    state["now"] += 3601.0

    # Should acquire without sleeping now
    limiter.acquire()
    assert sleep_calls == [], "After clock advance past 3600s, old grants must be pruned"


# ---------------------------------------------------------------------------
# Test 4: sanitize strips minLength recursively
# ---------------------------------------------------------------------------


def test_sanitize_strips_minlength_recursively() -> None:
    from eval.llm_clients.rate_limit import sanitize_response_format  # type: ignore[import-not-found]

    rf = {
        "type": "json_schema",
        "json_schema": {
            "name": "MyModel",
            "schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": "^\\S",
                        "description": "the text",
                    },
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 10,
                        "items": {"type": "string", "format": "uri"},
                    },
                },
                "maxLength": 999,  # top-level unsupported key
            },
        },
        "strict": True,
    }

    # Keep a copy to verify immutability
    import copy
    original_deep = copy.deepcopy(rf)

    result = sanitize_response_format(rf)

    # Original not mutated
    assert rf == original_deep

    # Verify unsupported keys removed at all levels
    schema = result["json_schema"]["schema"]  # type: ignore[index]
    assert "maxLength" not in schema

    text_prop = schema["properties"]["text"]  # type: ignore[index]
    assert "minLength" not in text_prop
    assert "pattern" not in text_prop
    assert text_prop["description"] == "the text"  # safe keys preserved
    assert text_prop["type"] == "string"

    items_prop = schema["properties"]["items"]  # type: ignore[index]
    assert "minItems" not in items_prop
    assert "maxItems" not in items_prop
    assert "format" not in items_prop["items"]

    # Non-unsupported keys preserved
    assert result["strict"] is True  # type: ignore[index]
    assert result["type"] == "json_schema"  # type: ignore[index]


# ---------------------------------------------------------------------------
# Test 5: sanitize passes through non-dict inputs
# ---------------------------------------------------------------------------


def test_sanitize_passes_through_non_dict() -> None:
    from eval.llm_clients.rate_limit import sanitize_response_format  # type: ignore[import-not-found]
    from pydantic import BaseModel

    class Dummy(BaseModel):
        value: str

    assert sanitize_response_format(Dummy) is Dummy
    assert sanitize_response_format("text") == "text"
    assert sanitize_response_format(None) is None
    assert sanitize_response_format(42) == 42


# ---------------------------------------------------------------------------
# Test 6: install is idempotent
# ---------------------------------------------------------------------------


def test_install_is_idempotent() -> None:
    from eval.llm_clients import rate_limit  # type: ignore[import-not-found]
    from eval.llm_clients.rate_limit import (  # type: ignore[import-not-found]
        install_global_rate_limit,
        uninstall_global_rate_limit,
    )

    clock, sleep, _ = make_fake_clock(0.0)
    limiter_a = rate_limit.SlidingWindowRateLimiter(
        1, 10, clock=clock, sleep=sleep, safety_factor=1.0
    )

    target = MagicMock()
    original_fn = MagicMock(return_value="original_result")
    target.create = original_fn

    install_global_rate_limit(_limiter=limiter_a, _target=target)
    first_wrapped = target.create

    # Second install — must be a no-op
    install_global_rate_limit(_limiter=limiter_a, _target=target)
    second_wrapped = target.create

    assert first_wrapped is second_wrapped, "Double-install must not re-wrap the function"
    assert rate_limit._installed is True

    uninstall_global_rate_limit(_target=target)
    assert rate_limit._installed is False


# ---------------------------------------------------------------------------
# Test 7: wrapper sanitizes response_format before passing to original
# ---------------------------------------------------------------------------


def test_wrapper_sanitizes_response_format() -> None:
    """The wrapped create strips minLength from a dict response_format before
    forwarding to the original callable."""
    from eval.llm_clients import rate_limit  # type: ignore[import-not-found]
    from eval.llm_clients.rate_limit import (  # type: ignore[import-not-found]
        install_global_rate_limit,
        uninstall_global_rate_limit,
    )

    clock, sleep, _ = make_fake_clock(0.0)
    limiter = rate_limit.SlidingWindowRateLimiter(
        max_per_min=100, max_per_hour=1000, clock=clock, sleep=sleep, safety_factor=1.0
    )

    original_fn = MagicMock(return_value="result")
    target = MagicMock()
    target.create = original_fn

    install_global_rate_limit(_limiter=limiter, _target=target)

    rf_with_minlength: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": "Test",
            "schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "minLength": 1}
                },
            },
        },
    }

    # Call the wrapper (it's now on target.create)
    target.create(
        MagicMock(),  # self
        messages=[{"role": "user", "content": "hi"}],
        model="test",
        response_format=rf_with_minlength,
    )

    # Inspect what the original received
    _, kwargs = original_fn.call_args
    sanitised_rf = kwargs["response_format"]
    text_schema = sanitised_rf["json_schema"]["schema"]["properties"]["text"]
    assert "minLength" not in text_schema
    assert text_schema["type"] == "string"


# ---------------------------------------------------------------------------
# Test 8: wrapper retries on RateLimitError then succeeds
# ---------------------------------------------------------------------------


def test_wrapper_retries_on_rate_limit_error_then_succeeds() -> None:
    """If the original raises a RateLimitError once, the wrapper retries and
    returns the successful result; sleep is called once."""
    from eval.llm_clients import rate_limit  # type: ignore[import-not-found]
    from eval.llm_clients.rate_limit import (  # type: ignore[import-not-found]
        install_global_rate_limit,
        uninstall_global_rate_limit,
    )

    clock, fake_sleep, state = make_fake_clock(0.0)
    sleep_calls: list[float] = []

    def tracking_sleep(s: float) -> None:
        sleep_calls.append(s)
        state["now"] += s

    limiter = rate_limit.SlidingWindowRateLimiter(
        max_per_min=100, max_per_hour=1000, clock=clock, sleep=tracking_sleep, safety_factor=1.0
    )

    # Build a fake RateLimitError that triggers the retry path.
    # We simulate it as a generic exception whose string contains "429".
    call_count = 0

    def flaky_create(self_arg: Any, *args: Any, **kwargs: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("429 request_quota_exceeded")
        return "success"

    original_fn = flaky_create
    target = MagicMock()
    target.create = original_fn

    # Patch time.sleep inside rate_limit module so retry backoff doesn't
    # actually sleep in the test.
    with patch.object(rate_limit._time_mod, "sleep", tracking_sleep):
        install_global_rate_limit(_limiter=limiter, _target=target, max_retries=3)

        result = target.create(
            MagicMock(),
            messages=[{"role": "user", "content": "hi"}],
            model="test",
        )

    assert result == "success"
    assert call_count == 2, "Should have called original exactly twice"
    # One retry-after sleep should have been triggered (backoff for attempt 0)
    assert len(sleep_calls) >= 1
