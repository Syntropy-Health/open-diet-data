"""Runtime Braintrust tracing for kg-mcp tool handlers.

Wraps each tool invocation in a span so production calls land in the same
Braintrust project (``shrine-diet-bioactivity``) as the test traces. Lets us
correlate a live agent's tool call to its result shape (chain count, answer
length, error class) without scraping PostHog properties.

Soft-import + fail-soft: a missing ``BRAINTRUST_API_KEY``, missing
``braintrust`` SDK, or span error never breaks the calling tool. Tracing is
strictly additive — disable by unsetting the API key.

This mirrors ``mcp/tests/e2e/_braintrust_logger.py`` but targets runtime tool
spans (type="tool") rather than test spans (type="test"). Kept separate so
the test helper can evolve independently without touching the runtime path.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

_BT_LOGGER: Any = None
_INIT_ATTEMPTED: bool = False
_DEFAULT_BRAINTRUST_PROJECT = "shrine-diet-bioactivity"


def _maybe_init() -> Any:
    global _BT_LOGGER, _INIT_ATTEMPTED
    if _INIT_ATTEMPTED:
        return _BT_LOGGER
    _INIT_ATTEMPTED = True

    api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not api_key:
        logger.debug("BRAINTRUST_API_KEY not set; runtime tracing disabled")
        return None

    try:
        import braintrust  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("braintrust SDK not installed; runtime tracing disabled")
        return None

    project = os.environ.get("BRAINTRUST_PROJECT") or _DEFAULT_BRAINTRUST_PROJECT
    try:
        _BT_LOGGER = braintrust.init_logger(project=project, api_key=api_key)
        logger.info("Braintrust runtime logger initialized for project %r", project)
        return _BT_LOGGER
    except Exception as exc:  # noqa: BLE001 — never let init break a tool call
        logger.warning("Failed to initialize Braintrust runtime logger: %s", exc)
        return None


class _NoOpSpan:
    """No-op stub yielded when Braintrust is disabled."""

    id: None = None  # mirrors the real span's .id so callers can getattr(span, "id", None)

    def log(self, **kwargs: Any) -> None:
        _ = kwargs
        return None

    def end(self) -> None:
        return None


def span_id(span: Any) -> Optional[str]:
    """Return the Braintrust span's UUID, or None for no-op spans / when disabled.

    Safe to call unconditionally — real Braintrust spans expose ``.id`` as a
    UUID-like string; ``_NoOpSpan`` and any span that lacks ``.id`` return None.
    """
    return getattr(span, "id", None)


@contextlib.contextmanager
def tool_span(name: str, **inputs: Any) -> Iterator[Any]:
    """Yield a Braintrust span (or no-op stub) for a runtime tool call.

    Span ``type`` is ``"tool"`` so live tool invocations are visually
    distinct from test spans in the Braintrust UI. ``inputs`` is recorded
    as the span's input payload — pass the tool arguments (e.g.
    ``seed``, ``top_k``, ``mode``) so retroactive debugging has the
    request shape on hand.
    """
    bt = _maybe_init()
    if bt is None:
        yield _NoOpSpan()
        return

    span: Any
    try:
        span = bt.start_span(name=name, type="tool", input=inputs)
    except Exception as exc:  # noqa: BLE001 — fail-soft on span start
        logger.warning("tool_span %r start failed: %s", name, exc)
        yield _NoOpSpan()
        return

    try:
        yield span
    finally:
        try:
            span.end()
        except Exception as exc:  # noqa: BLE001 — fail-soft on span end
            logger.debug("tool_span %r end failed: %s", name, exc)
