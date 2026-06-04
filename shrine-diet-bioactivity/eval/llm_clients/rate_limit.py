"""Process-global rate limiter, response-format sanitizer, and 429-retry wrapper
for the Cerebras free-tier LLM API.

Cerebras free-tier caps (live-read from response headers):
  - 5 requests / minute
  - 150 requests / hour   ← binding constraint for the 880-call eval matrix
  - 2 400 requests / day
  - 30 000 tokens / minute
  - 1 000 000 tokens / day

``install_global_rate_limit()`` monkeypatches ``openai.resources.chat.completions.Completions.create``
once, covering BOTH direct-client baselines AND the AG2 panel path (both go through
the openai SDK). The patch is idempotent and reversible via ``uninstall_global_rate_limit()``.
"""
from __future__ import annotations

import functools
import logging
import os
import threading
import time as _time_mod
from collections import deque
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state for idempotent install / uninstall
# ---------------------------------------------------------------------------

_installed: bool = False
_original_create: Any = None  # stores the original Completions.create function
_LIMITER: "SlidingWindowRateLimiter | None" = None

# ---------------------------------------------------------------------------
# Component A: SlidingWindowRateLimiter
# ---------------------------------------------------------------------------


class SlidingWindowRateLimiter:
    """Enforces <= max_per_min requests in any 60s window AND
    <= max_per_hour in any 3600s window.  ``acquire()`` blocks (sleeps) until
    a slot is free under BOTH windows, then records the grant.

    Clock and sleep are injected for deterministic testing.

    Thread-safety note: the lock is held during inspection and the sleep
    decision (computing wait duration), then RELEASED before the actual
    ``sleep()`` call, then re-acquired before the next loop iteration.
    This means a second thread can slip through while the first is sleeping,
    which is intentional: the matrix runner is effectively single-threaded, so
    the lock is defensive rather than a hard serialiser.  Releasing during
    sleep avoids priority inversion when sleep durations are long (up to 3600s
    for hourly cap).
    """

    def __init__(
        self,
        max_per_min: int,
        max_per_hour: int,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        safety_factor: float = 0.9,
    ) -> None:
        self._clock = clock or _time_mod.monotonic
        self._sleep = sleep or _time_mod.sleep
        # Apply safety margin so we stay comfortably under the hard caps.
        self._max_min = max(1, int(max_per_min * safety_factor))
        self._max_hour = max(1, int(max_per_hour * safety_factor))
        self._grants: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until both windows have room, then record a grant."""
        _EPSILON = 0.05  # small buffer so the pruned grant actually falls outside the window

        while True:
            wait_secs: float = 0.0

            with self._lock:
                now = self._clock()

                # Prune grants older than 3600s
                while self._grants and (now - self._grants[0]) >= 3600.0:
                    self._grants.popleft()

                # Grants within last 60s (min window)
                min_window_grants = [g for g in self._grants if (now - g) < 60.0]
                # All remaining grants are within 3600s (hour window)
                hour_count = len(self._grants)
                min_count = len(min_window_grants)

                if min_count < self._max_min and hour_count < self._max_hour:
                    # Both windows have room — record grant and return
                    self._grants.append(now)
                    return

                # Compute required waits for whichever windows are full
                if min_count >= self._max_min:
                    # Oldest grant in the min window
                    oldest_min = min_window_grants[0]
                    wait_min = 60.0 - (now - oldest_min) + _EPSILON
                    wait_secs = max(wait_secs, wait_min)

                if hour_count >= self._max_hour:
                    oldest_hour = self._grants[0]
                    wait_hour = 3600.0 - (now - oldest_hour) + _EPSILON
                    wait_secs = max(wait_secs, wait_hour)

            # Sleep outside the lock so other threads aren't blocked
            if wait_secs > 0:
                if wait_secs > 5:
                    logger.info("rate-limit pacing: sleeping %.1fs", wait_secs)
                self._sleep(wait_secs)

    @property
    def max_min(self) -> int:
        return self._max_min

    @property
    def max_hour(self) -> int:
        return self._max_hour


# ---------------------------------------------------------------------------
# Component B: sanitize_response_format
# ---------------------------------------------------------------------------

_UNSUPPORTED: frozenset[str] = frozenset(
    {"minLength", "maxLength", "pattern", "minItems", "maxItems", "format"}
)


def sanitize_response_format(rf: object) -> object:
    """Strip JSON-schema keywords Cerebras rejects from a response_format dict.

    Recursively removes: minLength, maxLength, pattern, minItems, maxItems, format.
    Non-dict inputs (e.g. a Pydantic class, a string) are returned unchanged —
    AG2/openai will serialise those themselves; we only sanitise already-dict
    json_schema payloads.

    Returns a NEW structure; the input is never mutated (immutability).
    """
    if not isinstance(rf, dict):
        return rf

    # Build a new dict, skipping unsupported keys, recursing into values
    new: dict[str, Any] = {}
    for k, v in rf.items():
        if k in _UNSUPPORTED:
            continue
        if isinstance(v, dict):
            new[k] = sanitize_response_format(v)
        elif isinstance(v, list):
            new[k] = [
                sanitize_response_format(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            new[k] = v
    return new


# ---------------------------------------------------------------------------
# Component C: install_global_rate_limit + retry wrapper
# ---------------------------------------------------------------------------

_DEFAULT_MAX_RPM = 5
_DEFAULT_MAX_RPH = 150
_DEFAULT_MAX_RETRIES = 8


def _make_wrapper(
    original: Any,
    limiter: "SlidingWindowRateLimiter",
    max_retries: int,
) -> Any:
    """Return a wrapped version of ``original`` with rate-limiting and retry."""

    @functools.wraps(original)
    def _wrapper(self_or_cls: Any, *args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        # 1. Sanitize response_format if it's a dict
        if "response_format" in kwargs and isinstance(kwargs["response_format"], dict):
            kwargs["response_format"] = sanitize_response_format(kwargs["response_format"])

        last_exc: BaseException | None = None
        for attempt in range(max_retries + 1):
            # 2. Acquire a rate-limit slot before each attempt
            limiter.acquire()

            try:
                return original(self_or_cls, *args, **kwargs)
            except Exception as exc:
                last_exc = exc
                exc_str = str(exc).lower()
                is_rate_limit = _is_rate_limit_error(exc, exc_str)

                if not is_rate_limit or attempt >= max_retries:
                    raise

                # Determine backoff duration
                sleep_secs = _compute_backoff(exc, exc_str, attempt)
                logger.warning(
                    "Cerebras 429 (%s); retry %d/%d after %.1fs",
                    _extract_code(exc_str),
                    attempt + 1,
                    max_retries,
                    sleep_secs,
                )
                _time_mod.sleep(sleep_secs)

        # Should not reach here, but satisfy type checker
        assert last_exc is not None
        raise last_exc

    return _wrapper


def _is_rate_limit_error(exc: BaseException, exc_str: str) -> bool:
    """Return True for 429 / quota / rate-limit errors."""
    try:
        import openai
        if isinstance(exc, openai.RateLimitError):
            return True
    except ImportError:
        pass
    return any(token in exc_str for token in ("429", "quota", "rate limit", "ratelimit"))


def _extract_code(exc_str: str) -> str:
    """Extract a short error code label for logging."""
    for label in ("request_quota_exceeded", "token_quota_exceeded", "queue_exceeded"):
        if label in exc_str:
            return label
    return "rate_limit"


def _compute_backoff(exc: BaseException, exc_str: str, attempt: int) -> float:
    """Return seconds to sleep before the next retry attempt."""
    # Honour Retry-After header if the SDK surfaces it
    retry_after: float | None = None
    if hasattr(exc, "response") and exc.response is not None:  # type: ignore[union-attr]
        try:
            ra = exc.response.headers.get("retry-after") or exc.response.headers.get("Retry-After")  # type: ignore[union-attr]
            if ra:
                retry_after = float(ra)
        except Exception:
            pass

    if retry_after is not None:
        return retry_after

    # Hourly quota errors need a long minimum back-off; limiter should prevent
    # these but this is the safety net.
    if "request_quota_exceeded" in exc_str:
        base = max(60.0, min(90.0, 2 ** attempt))
    else:
        base = min(90.0, 2 ** attempt)

    return base


def install_global_rate_limit(
    *,
    max_per_min: int | None = None,
    max_per_hour: int | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    _limiter: "SlidingWindowRateLimiter | None" = None,
    _target: Any = None,
) -> None:
    """Monkeypatch ``openai.resources.chat.completions.Completions.create`` to:

    1. Sanitise ``response_format`` (strip minLength/maxLength/etc.).
    2. Pace via a module-global ``SlidingWindowRateLimiter``.
    3. Retry on ``RateLimitError`` / 429, honouring ``Retry-After``.

    Idempotent: a second call is a no-op.

    Caps default from env ``CEREBRAS_MAX_RPM`` (default 5) / ``CEREBRAS_MAX_RPH``
    (default 150), or from the explicit keyword args.

    ``_limiter`` and ``_target`` are injection seams for unit tests — production
    callers should leave them as ``None``.
    """
    global _installed, _original_create, _LIMITER  # noqa: PLW0603

    if _installed:
        return

    rpm = max_per_min or int(os.environ.get("CEREBRAS_MAX_RPM", _DEFAULT_MAX_RPM))
    rph = max_per_hour or int(os.environ.get("CEREBRAS_MAX_RPH", _DEFAULT_MAX_RPH))

    if _limiter is not None:
        limiter = _limiter
    else:
        limiter = SlidingWindowRateLimiter(
            max_per_min=rpm,
            max_per_hour=rph,
        )

    _LIMITER = limiter

    if _target is not None:
        # Test seam: patch the injected target object instead of the real SDK
        original = _target.create
        wrapper = _make_wrapper(original, limiter, max_retries)
        _target.create = wrapper
        _original_create = original
    else:
        from openai.resources.chat.completions import Completions  # noqa: PLC0415
        original = Completions.__dict__["create"]  # unbound function
        wrapper = _make_wrapper(original, limiter, max_retries)
        Completions.create = wrapper  # type: ignore[method-assign]
        _original_create = original

    _installed = True
    logger.debug(
        "install_global_rate_limit: patched Completions.create "
        "(rpm_cap=%d, rph_cap=%d, max_retries=%d)",
        limiter.max_min,
        limiter.max_hour,
        max_retries,
    )


def uninstall_global_rate_limit(_target: Any = None) -> None:
    """Restore the original ``Completions.create`` and reset module state.

    Provided for test teardown to prevent the monkeypatch from leaking across
    test modules.  ``_target`` must match what was passed to
    ``install_global_rate_limit`` (or ``None`` for the real SDK).
    """
    global _installed, _original_create, _LIMITER  # noqa: PLW0603

    if not _installed:
        return

    if _original_create is None:
        return

    if _target is not None:
        _target.create = _original_create
    else:
        from openai.resources.chat.completions import Completions  # noqa: PLC0415
        Completions.create = _original_create  # type: ignore[method-assign]

    _installed = False
    _original_create = None
    _LIMITER = None
