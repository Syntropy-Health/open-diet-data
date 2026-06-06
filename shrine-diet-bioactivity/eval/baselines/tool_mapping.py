"""Maps v1 paper-1 Layer-B retrieval intents to the deployed kg-mcp v1 tool surface.

Each entry is a list of MCP tool calls to execute sequentially. Most v1
intents are SINGLE-STEP plans because each v1 tool is a Layer-B/C primitive
that performs the full traversal internally (unlike the earlier two-step
semantic-search + get-subgraph pattern).

Earlier calls' outputs can still feed into later calls' args via
{{ template-ref }} fields; the executor's prev-handling logic is generic
and unchanged.

Implemented as data so the eval pipeline can introspect the plan + cite
each call's bt_span_id in case studies.
"""
from __future__ import annotations

from typing import Any

RETRIEVAL_PLAN_BY_INTENT: dict[str, list[dict[str, Any]]] = {
    "kg_query": [
        {"tool": "kg_query", "args": {"question": "{{ question }}", "mode": "hybrid"}},
    ],
    "diet_to_compounds": [
        {"tool": "kg_diet_to_compounds", "args": {"seed": "{{ seed }}"}},
    ],
    "compound_to_targets": [
        {"tool": "kg_compound_to_targets", "args": {"seed": "{{ seed }}"}},
    ],
    "compound_to_diseases": [
        {"tool": "kg_compound_to_diseases", "args": {"seed": "{{ seed }}"}},
    ],
    "herb_to_diseases": [
        {"tool": "kg_herb_to_diseases", "args": {"seed": "{{ seed }}"}},
    ],
    "herb_to_symptoms": [
        {"tool": "kg_herb_to_symptoms", "args": {"seed": "{{ seed }}"}},
    ],
    "compound_to_symptoms": [
        {"tool": "kg_compound_to_symptoms", "args": {"seed": "{{ seed }}"}},
    ],
    "hdi_check": [
        # Direct interaction lookup (authoritative when present, but the
        # HDI-Safe-50 panel is sparse for many pairs → often found=false).
        {"tool": "kg_hdi_check", "args": {"herb": "{{ herb }}", "drug": "{{ drug }}"}},
        # Mechanism evidence: the herb's pharmacological/clinical profile.
        # kg_herb_to_symptoms returns ~20 chains for canonical binomials
        # (e.g. Hypericum perforatum) where kg_hdi_check / kg_herb_to_diseases
        # return nothing — this is what gives the panel real KG grounding on
        # HDI scenarios so the safety judgment is evidence-backed, not just
        # gold-red-flag-driven.
        {"tool": "kg_herb_to_symptoms", "args": {"seed": "{{ herb }}"}},
    ],
    "bilingual_term": [
        {"tool": "kg_bilingual_term", "args": {"term": "{{ term }}"}},
    ],
    "node_neighborhood": [
        {"tool": "kg_node_neighborhood", "args": {"seed": "{{ seed }}"}},
    ],
}


def list_intents() -> list[str]:
    """Return the v1 retrieval intent names (for traceability)."""
    return list(RETRIEVAL_PLAN_BY_INTENT.keys())
