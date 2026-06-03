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


def _resolve_template(value: Any, bindings: dict[str, Any], prev: Any) -> Any:
    if isinstance(value, str):
        def sub(m: re.Match[str]) -> str:  # type: ignore[type-arg]
            expr = m.group(1)
            if expr.startswith("prev"):
                return _resolve_path(prev, expr)
            return str(bindings.get(expr, ""))
        return _TEMPLATE_RE.sub(sub, value)
    if isinstance(value, dict):
        return {k: _resolve_template(v, bindings, prev) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_template(v, bindings, prev) for v in value]
    return value


def _resolve_path(obj: Any, path: str) -> str:
    """Resolve dotted/bracketed access like prev.entities[0].id.

    Returns "" when obj is None (plan referenced prev before any tool call ran)
    or a path token can't be resolved — matches the executor's fail-soft semantics.
    """
    if obj is None:
        return ""
    tokens = re.findall(r"[^.\[\]]+", path)[1:]  # drop leading 'prev'
    cur: Any = obj
    for tok in tokens:
        if cur is None:
            return ""
        if tok.isdigit():
            cur = cur[int(tok)]
        else:
            cur = cur.get(tok) if isinstance(cur, dict) else getattr(cur, tok, None)
    return str(cur) if cur is not None else ""


class RetrievalExecutor:
    def __init__(self, mcp_client: MCPClient):
        self._mcp = mcp_client

    def execute(self, plan: list[dict[str, Any]], bindings: dict[str, Any]) -> RetrievalResult:
        result = RetrievalResult()
        prev: Any = None
        for step in plan:
            tool = step["tool"]
            args = _resolve_template(step.get("args", {}), bindings, prev)
            try:
                response = self._mcp.call_tool(tool=tool, args=args)
            except Exception as exc:
                result.error = str(exc)
                return result
            result.chains.append(response)
            span_id = response.get("_bt_span_id") if isinstance(response, dict) else None
            if span_id:
                result.bt_span_ids.append(span_id)
            prev = response
        return result
