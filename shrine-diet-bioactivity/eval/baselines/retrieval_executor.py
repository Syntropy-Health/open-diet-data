"""Executes a retrieval plan (list of MCP tool calls with template bindings)
against the live kg-mcp gateway and collects bt_span_id provenance.

A retrieval plan is the output of eval.baselines.tool_mapping.RETRIEVAL_PLAN_BY_INTENT
— a list of dicts with a 'tool' name and 'args' dict containing {{ template }}
placeholders. Templates resolve from caller-supplied bindings (e.g. {{ seed }})
or from the previous response (e.g. {{ prev.entities[0].id }}).

On per-call exception: stops execution, records the error string, returns
whatever chains + span_ids were collected up to that point. Never raises.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol


class MCPClient(Protocol):
    def call_tool(self, *, tool: str, args: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class RetrievalResult:
    chains: list[dict[str, Any]] = field(default_factory=list)
    bt_span_ids: list[str] = field(default_factory=list)
    error: str | None = None


_TEMPLATE_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def _resolve_template(value: Any, bindings: dict[str, Any], prev_history: list[Any]) -> Any:
    if isinstance(value, str):
        def sub(m: re.Match[str]) -> str:  # type: ignore[type-arg]
            expr = m.group(1)
            if expr.startswith("prev"):
                return _resolve_path(prev_history, expr)
            return str(bindings.get(expr, ""))
        return _TEMPLATE_RE.sub(sub, value)
    if isinstance(value, dict):
        return {k: _resolve_template(v, bindings, prev_history) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_template(v, bindings, prev_history) for v in value]
    return value


def _resolve_path(prev_history: list[Any], path: str) -> str:
    """Resolve dotted/bracketed access against prev-call history.

    Two access patterns are supported:
      - `prev.X.Y`        → most recent response's X.Y (history[-1].X.Y).
      - `prev[N].X.Y`     → step-N response's X.Y (history[N].X.Y).

    Returns "" when:
      - prev_history is empty (template referenced before any call ran),
      - a numeric index is out of range,
      - or any token along the path can't be resolved.
    This matches the executor's fail-soft contract (no exceptions raised
    upward; failures degrade to empty-string template substitutions).
    """
    if not prev_history:
        return ""
    tokens = re.findall(r"[^.\[\]]+", path)
    # tokens[0] is always "prev". If tokens[1] is a digit, it indexes prev_history.
    if len(tokens) >= 2 and tokens[1].isdigit():
        idx = int(tokens[1])
        if idx >= len(prev_history) or idx < -len(prev_history):
            return ""
        cur: Any = prev_history[idx]
        remaining = tokens[2:]
    else:
        cur = prev_history[-1]
        remaining = tokens[1:]
    for tok in remaining:
        if cur is None:
            return ""
        if tok.isdigit():
            try:
                cur = cur[int(tok)]
            except (KeyError, IndexError, TypeError):
                return ""
        else:
            cur = cur.get(tok) if isinstance(cur, dict) else getattr(cur, tok, None)
    return str(cur) if cur is not None else ""


class RetrievalExecutor:
    def __init__(self, mcp_client: MCPClient):
        self._mcp = mcp_client

    def execute(self, plan: list[dict[str, Any]], bindings: dict[str, Any]) -> RetrievalResult:
        result = RetrievalResult()
        prev_history: list[Any] = []
        for step in plan:
            tool = step["tool"]
            args = _resolve_template(step.get("args", {}), bindings, prev_history)
            try:
                response = self._mcp.call_tool(tool=tool, args=args)
            except Exception as exc:
                result.error = str(exc)
                return result
            result.chains.append(response)
            span_id = response.get("_bt_span_id") if isinstance(response, dict) else None
            if span_id:
                result.bt_span_ids.append(span_id)
            prev_history.append(response)
        return result
