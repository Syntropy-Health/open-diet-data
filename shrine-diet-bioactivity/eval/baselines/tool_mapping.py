"""Maps v1 paper-1 Layer-B retrieval intents to the new kg-mcp tool surface.

Each entry is a list of MCP tool calls to execute sequentially. Earlier
calls' outputs feed into later calls' args via {{ template-ref }} fields.
Implemented as data so the eval pipeline can introspect the plan + cite
each call's bt_span_id in case studies.
"""
from __future__ import annotations

from typing import Any

RETRIEVAL_PLAN_BY_INTENT: dict[str, list[dict[str, Any]]] = {
    "kg_query": [
        {"tool": "semantic-search", "args": {"query": "{{ question }}", "top_k": 5}},
        {"tool": "get-entity", "args": {"entity_id": "{{ prev.entities[0].id }}"}},
    ],
    "diet_to_compounds": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "labels": ["Diet"], "top_k": 3}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["CONTAINS"]}, "depth": 2},
    ],
    "compound_to_targets": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "labels": ["Compound"], "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["BINDS", "INHIBITS", "MODULATES"]}, "depth": 1},
    ],
    "compound_to_diseases": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "labels": ["Compound"], "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["TREATS", "MODULATES", "AFFECTS"]}, "depth": 2},
    ],
    "herb_to_diseases": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "labels": ["Herb"], "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["TREATS", "INDICATED_FOR"]}, "depth": 2},
    ],
    "herb_to_symptoms": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "labels": ["Herb"], "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["RELIEVES", "TREATS"]}, "depth": 2},
    ],
    "compound_to_symptoms": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "labels": ["Compound"], "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["RELIEVES", "MODULATES"]}, "depth": 2},
    ],
    "hdi_check": [
        {"tool": "semantic-search", "args": {"query": "{{ herb }}", "labels": ["Herb"], "top_k": 1}},
        {"tool": "semantic-search", "args": {"query": "{{ drug }}", "labels": ["Compound", "Drug"], "top_k": 1}},
        {
            "tool": "get-subgraph",
            "args": {"start": "{{ prev[0].entities[0].id }}", "edges": ["INTERACTS_WITH"]},
            "depth": 2,
            "start_from_intersection": True,
            "second_start": "{{ prev[1].entities[0].id }}",
        },
    ],
    "bilingual_term": [
        {"tool": "semantic-search", "args": {"query": "{{ term }}", "labels": ["Herb", "Compound"], "top_k": 3}, "lang_filter": "auto"},
    ],
    "node_neighborhood": [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}", "edges": ["*"]}, "depth": 1},
    ],
}


def list_intents() -> list[str]:
    """Return the v1 retrieval intent names (for traceability)."""
    return list(RETRIEVAL_PLAN_BY_INTENT.keys())
