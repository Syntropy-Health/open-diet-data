"""Thin MCP client wrapper for the kg-mcp gateway.

Exposes call_tool(tool, args) which performs the streamable-HTTP MCP
handshake, posts a tools/call, parses the SSE/JSON response, and
attaches `_bt_span_id` (sourced from the X-Braintrust-Span-Id response
header set by PR #92's braintrust_runtime.tool_span) so callers can
record provenance for §A.3 case studies.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class MCPClient:
    url: str
    token: str
    session: Any = None  # httpx.Client or compatible mock
    _session_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = httpx.Client(timeout=60)

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            h["mcp-session-id"] = self._session_id
        return h

    def _ensure_initialized(self) -> None:
        if self._session_id is not None:
            return
        r = self.session.post(
            self.url,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "eval-runner", "version": "0.1"},
                },
            },
        )
        r.raise_for_status()
        self._session_id = r.headers.get("mcp-session-id") or str(uuid.uuid4())
        self.session.post(
            self.url,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )

    @staticmethod
    def _parse_sse_or_json(text: str) -> dict[str, Any]:
        for line in text.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(text)

    def call_tool(self, *, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        self._ensure_initialized()
        r = self.session.post(
            self.url,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
        )
        r.raise_for_status()
        payload = self._parse_sse_or_json(r.text)
        result = payload.get("result", {})
        span_id = r.headers.get("X-Braintrust-Span-Id")
        if span_id:
            result["_bt_span_id"] = span_id
        return result


def build_mcp_client() -> MCPClient:
    url = os.environ.get("KG_MCP_E2E_URL")
    token = os.environ.get("KG_MCP_API_KEY")
    if not url or not token:
        raise RuntimeError("KG_MCP_E2E_URL and KG_MCP_API_KEY must both be set")
    normalized = url.rstrip("/") + "/mcp" if not url.rstrip("/").endswith("/mcp") else url.rstrip("/")
    return MCPClient(url=normalized, token=token)
