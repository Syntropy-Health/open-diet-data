"""Agentic E2E — minimal Anthropic SDK tool-use loop against live kg-mcp.

Goal: prove an LLM agent, given only the gateway URL + bearer token,
can successfully ground a clinical-style question on the live KG. Locks
the "functional prototype readiness" criterion the migration is in
service of (Phase 5 of the plan).

Loop is intentionally tiny — one tool registered (``kg_query``), one
back-and-forth, then we assert the agent's reply cites at least one
provenance source_id matching the documented prefix regex.

Gating: three env vars must all be present, or the test skips cleanly:

  * ``KG_MCP_E2E_URL``      — gateway base URL, e.g. ``https://kg-mcp-test.up.railway.app``
  * ``KG_MCP_API_KEY``      — bearer token enforced on /mcp
  * ``ANTHROPIC_API_KEY``   — for the SDK loop

Why not AG2: AG2 is heavyweight (multi-agent orchestration). For a single
tool-use loop, the bare Anthropic SDK is one file and avoids pulling AG2
into the kg-mcp test path. Per architectural choice in /plan discussion.
"""
from __future__ import annotations

import json
import os
import re

import httpx
import pytest

from ._braintrust_logger import bt_span


pytestmark = [pytest.mark.e2e]


_SOURCE_PREFIX = re.compile(
    r"\b(duke|cmaup|herb2|symmap|hdi-safe-50|opentcm|food):[A-Za-z0-9_\-]+",
    re.IGNORECASE,
)


def _env_or_skip(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} not set; agentic E2E skipped.")
    return value


# ---------------------------------------------------------------------------
# Minimal kg-mcp client — initialise, call one tool, return the typed payload
# ---------------------------------------------------------------------------


def _mcp_call(url: str, key: str, tool: str, arguments: dict) -> dict:
    """Invoke a single MCP tool via streamable-HTTP. Returns the typed
    structuredContent payload (or the envelope dict on isError)."""
    h = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=60.0) as c:
        # initialize
        r = c.post(
            f"{url}/mcp",
            headers=h,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agentic-e2e", "version": "0.1"},
                },
            },
        )
        r.raise_for_status()
        sid = r.headers["mcp-session-id"]
        h2 = {**h, "mcp-session-id": sid}
        c.post(
            f"{url}/mcp",
            headers=h2,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        # tools/call
        r = c.post(
            f"{url}/mcp",
            headers=h2,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
        )
        r.raise_for_status()
        body = None
        for line in r.text.splitlines():
            if line.startswith("data: "):
                body = json.loads(line[6:])
                break
        if body is None:
            body = r.json()
        envelope = body.get("result", {}) or {}
        return envelope.get("structuredContent") or envelope


# ---------------------------------------------------------------------------
# The actual agentic loop
# ---------------------------------------------------------------------------


def test_agent_uses_kg_query_and_cites_provenance():
    """One-turn agentic loop: the model picks a KG tool (kg_query or
    kg_herb_to_symptoms), gets a real payload, and produces a final reply
    that cites ≥ 1 provenance source_id matching the documented prefix
    regex (e.g. ``duke:treats_symptom``).

    Both Layer-A (kg_query) and Layer-B (kg_herb_to_symptoms) are
    registered so the agent can pick the right tool for the question;
    Layer-B traversals return per-edge source_ids while Layer-A may not.

    A skip-clean PRO TIP: pre-fund OpenRouter / Anthropic in CI with a
    tiny budget; the loop costs < $0.005 per run.
    """
    url = _env_or_skip("KG_MCP_E2E_URL")
    key = _env_or_skip("KG_MCP_API_KEY")
    anthropic_key = _env_or_skip("ANTHROPIC_API_KEY")

    try:
        from anthropic import Anthropic
    except ImportError:
        pytest.skip("anthropic SDK not installed in this test env.")

    client = Anthropic(api_key=anthropic_key)
    tools = [
        {
            "name": "kg_query",
            "description": (
                "Layer-A natural-language Q&A over the LightRAG KG. Use this "
                "for open-ended exploration. Returns a synthesized prose "
                "answer plus a references array. NOTE: references may be "
                "empty for some queries — prefer kg_herb_to_symptoms when the "
                "question is about which symptoms an herb treats."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural-language question about diet/herbs/compounds.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["local", "global", "hybrid", "naive", "mix"],
                        "default": "local",
                    },
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["question"],
            },
        },
        {
            "name": "kg_herb_to_symptoms",
            "description": (
                "Layer-B role-priored traversal: Herb → Symptom. Seed with an "
                "herb name (e.g. 'Astragalus membranaceus'). Returns chains of "
                "edges, each with a source_id in the documented "
                "`<prefix>:<id>` format (e.g. 'duke:treats_symptom'). PREFER "
                "this over kg_query when the question is about which symptoms "
                "or conditions an herb treats — it returns explicitly-cited "
                "provenance per edge."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "seed": {
                        "type": "string",
                        "description": "Herb name (binomial preferred).",
                    },
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["seed"],
            },
        },
    ]
    system_msg = (
        "You are a clinical-knowledge agent grounding answers in the Syntropy "
        "diet knowledge graph. You MUST follow these rules in every reply:\n"
        "1. Call a KG tool first; do not answer from prior knowledge. For "
        "questions about which symptoms or conditions an herb treats, prefer "
        "kg_herb_to_symptoms (it returns explicitly-cited source_ids per "
        "edge). Use kg_query only for open-ended exploration.\n"
        "2. Read the tool result and quote at least one source_id verbatim "
        "from the chains / edges / references array. Source IDs always look "
        "like `<prefix>:<identifier>` where <prefix> is one of "
        "duke, cmaup, herb2, symmap, hdi-safe-50, opentcm, food.\n"
        "3. If the tool returned no usable references AND another tool exists "
        "that might, call that tool instead before giving up. Only say 'no "
        "usable references' after you have exhausted the available tools.\n"
        "Your final reply MUST contain at least one literal token matching "
        "`<prefix>:<id>` from the tool result. Replies without a source_id "
        "are considered failed."
    )
    user_msg = (
        "Which symptoms does Astragalus membranaceus treat, and what is the "
        "provenance of the evidence? Pick the most appropriate KG tool, then "
        "quote the source_id of at least one supporting edge verbatim in "
        "your reply."
    )

    with bt_span(
        "test_agent_uses_kg_query_and_cites_provenance",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        gateway=url,
        user_msg=user_msg,
    ) as span:
        # Turn 1 — model decides whether to call the tool.
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_msg,
            tools=tools,
            messages=[{"role": "user", "content": user_msg}],
        )

        tool_use = next(
            (c for c in resp.content if getattr(c, "type", "") == "tool_use"),
            None,
        )
        assert tool_use is not None, (
            f"Model didn't call a KG tool. stop_reason={resp.stop_reason} "
            f"content={[c.type for c in resp.content]}"
        )
        assert tool_use.name in ("kg_query", "kg_herb_to_symptoms"), (
            f"Model called unexpected tool {tool_use.name!r}"
        )

        # Execute the tool against the live gateway.
        tool_result = _mcp_call(url, key, tool_use.name, dict(tool_use.input))

        # Turn 2 — feed the tool result back; model summarises.
        final = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_msg,
            tools=tools,
            messages=[
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": resp.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(tool_result)[:8000],
                        }
                    ],
                },
            ],
        )
        final_text = "\n".join(
            c.text for c in final.content if getattr(c, "type", "") == "text"
        )

        provenance_match = _SOURCE_PREFIX.search(final_text)
        span.log(
            output={
                "tool_called": tool_use.name,
                "tool_input": dict(tool_use.input),
                "final_text_len": len(final_text),
                "final_text_preview": final_text[:500],
                "provenance_source_id": provenance_match.group(0) if provenance_match else None,
                "stop_reason": final.stop_reason,
            }
        )
        assert final_text.strip(), f"empty final reply; got {final.content!r}"
        # Provenance discipline: the reply must include at least one
        # source_id matching the documented prefix regex. This is a strong
        # signal that the agent actually used the KG payload (rather than
        # hallucinating around it).
        assert provenance_match, (
            "Agent reply lacks a documented source_id prefix — provenance "
            f"discipline failed.\n--- reply ---\n{final_text[:800]}"
        )
