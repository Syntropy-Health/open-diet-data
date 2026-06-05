"""Single-LLM + kg-mcp semantic-search retrieval baseline.

Identical to single_llm but injects a flat RAG context from the kg-mcp
semantic-search tool into the system prompt. Gracefully degrades to
no-retrieval if the kg-mcp gateway is unreachable or env vars are unset
(any exception is caught, baseline proceeds without context).
"""
from __future__ import annotations

import json

from eval.llm_clients.cerebras import build_cerebras_client, CEREBRAS_DEFAULT_MODEL  # type: ignore[import-not-found]
from eval.mcp_clients import build_mcp_client  # type: ignore[import-not-found]

from agents.models import (  # type: ignore[import-not-found]
    ConfidenceComponents,
    PanelDeliberation,
    ResearchQuestion,
    ResearchSynthesis,
    RoleVerdict,
    Triage,
)
from eval.scenario import Scenario  # type: ignore[import-not-found]

_BARRIER_AGENT_SYSTEM = """\
You are a clinical research assistant with access to a knowledge graph context.
Given a research question about a herbal/dietary intervention and (optionally)
retrieved KG evidence chains, emit a JSON object with fields:
  verdict: one of prefer|caution|reject|abstain
  support: list of bullet-point strings supporting the intervention
  concerns: list of bullet-point strings raising concerns
  notes: short qualitative summary

Use the provided KG evidence to ground your claims where available.

VERDICT COMMITMENT REQUIREMENT: Commit to one of **prefer**, **caution**, or
**reject** based on the balance of available evidence — these are the only
outcomes the benchmark scores. Do NOT default to "abstain": reserve it strictly
for questions that are fundamentally unanswerable from any evidence (this should
essentially never happen for a well-formed clinical question). When evidence is
mixed or limited, choose **caution** rather than abstaining.

Emit ONLY valid JSON. No markdown fences. No preamble.
"""


def _build_kg_context(scenario: Scenario) -> tuple[str, list[str]]:
    """Retrieve via new kg-mcp semantic-search; return (context_str, bt_span_ids).

    Gracefully degrades on any error (gateway unreachable, env vars unset,
    parse failure) — matches v1's KGQueryError-catch semantics so the baseline
    still produces a verdict even when retrieval fails.
    """
    try:
        mcp = build_mcp_client()
        result = mcp.call_tool(
            tool="semantic-search",
            args={"query": scenario.research_question, "top_k": 10},
        )
    except Exception:
        return "", []

    span_id = result.get("_bt_span_id") if isinstance(result, dict) else None
    span_ids = [span_id] if span_id else []

    entities = result.get("entities", []) if isinstance(result, dict) else []
    if not entities:
        return "", span_ids

    lines = []
    for i, ent in enumerate(entities[:10]):
        ent_id = ent.get("id", "<unknown>")
        name = ent.get("name") or ent.get("label") or ""
        label_field = ent.get("label") or ent.get("type") or ""
        snippet = (ent.get("description") or ent.get("snippet") or "")[:200]
        lines.append(f"  [{i}] {ent_id}: {name} ({label_field}) — {snippet}")
    return "Retrieved KG evidence (semantic-search):\n" + "\n".join(lines), span_ids


def run(scenario: Scenario) -> ResearchSynthesis:
    """Single-LLM with kg-mcp semantic-search retrieval injected into system prompt."""
    kg_context, span_ids = _build_kg_context(scenario)

    system_prompt = _BARRIER_AGENT_SYSTEM
    if kg_context:
        system_prompt = system_prompt + "\n\n" + kg_context

    client = build_cerebras_client()
    reply = client.chat.completions.create(
        model=CEREBRAS_DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": scenario.research_question},
        ],
        temperature=0,
        max_tokens=1500,
        extra_body={"seed": 42},
    )
    raw = reply.choices[0].message.content or "{}"
    obj = _parse_json(raw)

    verdict = _coerce_verdict(obj.get("verdict", "abstain"))
    rq = ResearchQuestion(text=scenario.research_question)
    triage = Triage(
        complexity="low",
        rationale="single-LLM+RAG baseline (no triage step)",
        red_flags=[],
    )
    panel = PanelDeliberation(
        verdicts=[
            RoleVerdict(
                role="Dietitian",
                verdict=verdict,
                support=obj.get("support", []),
                concerns=obj.get("concerns", []),
                notes=obj.get("notes", ""),
            )
        ],
        dissent=[],
        moderator_summary=obj.get("notes", ""),
    )
    # Slightly higher evidence_tier if KG context was available
    evidence_tier = 0.4 if kg_context else 0.3
    components = ConfidenceComponents(
        evidence_tier=evidence_tier,
        hdi_risk=0.0,
        question_fit=0.5 if verdict == "prefer" else 0.2,
    )
    confidence = _simple_confidence(components)
    return ResearchSynthesis(
        question=rq,
        triage=triage,
        candidate_chains=[],
        panel=panel,
        confidence=confidence,
        components=components,
        defer_to_clinician=False,
        bt_span_ids=span_ids,
    )


def _parse_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return {}


def _coerce_verdict(v: str) -> str:
    allowed = {"prefer", "caution", "reject", "abstain"}
    return v if v in allowed else "abstain"


def _simple_confidence(c: ConfidenceComponents) -> float:
    eps = 1e-6
    score = (
        max(c.evidence_tier, eps) ** 0.5
        * max(1.0 - c.hdi_risk, eps) ** 0.3
        * max(c.question_fit, eps) ** 0.2
    )
    return min(max(score, 0.0), 1.0)
