"""Smoke tests locking the no-raise contract of braintrust_runtime.tool_span.

These are not E2E — they don't talk to Braintrust. They verify the helper's
fail-soft guarantees so a future edit can't silently break tool calls when
BRAINTRUST_API_KEY is unset or the SDK errors. The runtime path through
every kg-mcp tool handler depends on this contract.
"""
from __future__ import annotations

import pytest

from kg_mcp.braintrust_runtime import _NoOpSpan, span_id, tool_span

pytestmark = [pytest.mark.unit]


def test_tool_span_yields_noop_when_api_key_missing(monkeypatch):
    """No env key → no-op span. log() and end() must not raise."""
    monkeypatch.delenv("BRAINTRUST_API_KEY", raising=False)
    # Reset the module-level init memo so a stale prior call doesn't mask this.
    import kg_mcp.braintrust_runtime as br

    monkeypatch.setattr(br, "_INIT_ATTEMPTED", False)
    monkeypatch.setattr(br, "_BT_LOGGER", None)

    with tool_span("smoke_no_key", arg=1) as span:
        assert isinstance(span, _NoOpSpan)
        # All span-API methods used by the runtime path must be no-ops.
        span.log(output={"ok": True})
        span.end()


def test_tool_span_yields_noop_when_braintrust_sdk_import_fails(monkeypatch):
    """SDK missing → no-op span. Simulated by forcing ImportError on import."""
    monkeypatch.setenv("BRAINTRUST_API_KEY", "fake-key-for-test")
    import builtins

    import kg_mcp.braintrust_runtime as br

    monkeypatch.setattr(br, "_INIT_ATTEMPTED", False)
    monkeypatch.setattr(br, "_BT_LOGGER", None)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "braintrust":
            raise ImportError("simulated missing SDK")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with tool_span("smoke_no_sdk", arg=1) as span:
        assert isinstance(span, _NoOpSpan)
        span.log(output={"ok": True})


def test_noop_span_log_swallows_arbitrary_kwargs():
    """Tool handlers pass varied kwargs to span.log; none should raise."""
    span = _NoOpSpan()
    span.log()
    span.log(output={"chain_count": 5})
    span.log(error="ConnectionError", error_message="boom")
    span.end()


def test_noop_span_exposes_id_as_none():
    """_NoOpSpan.id must be None so tool handlers can read span.id without crashing.

    The eval pipeline reads bt_span_id from tool responses; when Braintrust is
    disabled the field should be null (serialised None) — never an AttributeError.
    Field name chosen: ``bt_span_id`` (no leading underscore) because Pydantic v2
    treats ``_``-prefixed names as private attributes and excludes them from
    model_dump() / JSON serialisation.
    """
    span = _NoOpSpan()
    assert span.id is None
    # getattr fallback form used in tool handlers must also be None
    assert getattr(span, "id", "MISSING") is None


def test_span_id_helper_returns_none_for_noop(monkeypatch):
    """span_id() must return None for a _NoOpSpan regardless of env state.

    This covers the path where BRAINTRUST_API_KEY is unset (the common CI case).
    """
    monkeypatch.delenv("BRAINTRUST_API_KEY", raising=False)
    import kg_mcp.braintrust_runtime as br

    monkeypatch.setattr(br, "_INIT_ATTEMPTED", False)
    monkeypatch.setattr(br, "_BT_LOGGER", None)

    with tool_span("helper_noop_test", x=1) as span:
        assert isinstance(span, _NoOpSpan)
        assert span_id(span) is None
