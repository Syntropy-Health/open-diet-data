"""Diet-OS wrapper baseline — pre-fetches retrieval via new kg-mcp tool surface
then runs the AG2 multi-agent panel via run_case_study with preset_kg.

Retrieval surface: post-PR#92 kg-mcp tools (semantic-search, get-subgraph,
get-entity) via eval.mcp_clients.MCPClient. Every call emits a Braintrust
span; span IDs are collected and threaded onto the returned ResearchSynthesis
as .bt_span_ids[] for §A.3 case-study provenance citations.

Eval-time triage bypass preserved: free-tier LLM triage was unreliable on
v1's Nemotron (33/40 parse failures). The C1 gold-triage substitute is
preserved here as the disclosed paper-1 v1 design.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from agents.models import (  # type: ignore[import-not-found]
    KGEdge,
    KGResult,
    ProvenanceChain,
    ResearchQuestion,
    ResearchSynthesis,
    Triage,
)
from agents.run_case_study import run_case_study  # type: ignore[import-not-found]
from eval.baselines.retrieval_executor import RetrievalExecutor  # type: ignore[import-not-found]
from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
from eval.llm_clients.cerebras import build_cerebras_client  # type: ignore[import-not-found]
from eval.mcp_clients import build_mcp_client  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]

# Mapping from scenario category to retrieval intent.
# Categories not listed fall back to "kg_query" (semantic-search only).
_INTENT_BY_CATEGORY: dict[str, str] = {
    "multi_drug_hdi": "hdi_check",
    "tcm_bilingual": "bilingual_term",
    "nutrition": "diet_to_compounds",
    "herbal_single_symptom": "herb_to_symptoms",
}

# Known v1 evidence tiers — strings outside this set are coerced to "unknown".
_LOCAL_EVIDENCE_TIERS = frozenset({
    "clinical_trial", "pharmacokinetic_study", "observational",
    "case_report_series", "case_report",
    "experimental", "in_vivo", "in_vitro",
    "traditional", "unknown",
})


def _intervention_from_scenario_id(scenario_id: str) -> str | None:
    """Heuristic extraction. Scenario ids follow the convention
    `case-<category>-<num>-<intervention-name>-<outcome>`. Token [3] is
    the intervention. Underscores → spaces, then title-case."""
    parts = scenario_id.split("-")
    if len(parts) < 4:
        return None
    raw = parts[3]
    if not raw:
        return None
    return raw.replace("_", " ").title()


def _scenario_to_preset(scenario: Scenario) -> tuple[ResearchQuestion, Triage]:
    rq = ResearchQuestion(
        text=scenario.research_question,
        intervention=_intervention_from_scenario_id(scenario.id),
        languages=list(scenario.gold.languages or ["en"]),
    )
    triage = Triage(
        complexity=scenario.gold.expected_complexity,
        rationale=f"eval-preset from gold.expected_complexity={scenario.gold.expected_complexity}",
        red_flags=list(scenario.gold.expected_red_flags or []),
    )
    return rq, triage


def _select_intent(scenario: Scenario) -> str:
    """Map scenario category to a retrieval intent key."""
    return _INTENT_BY_CATEGORY.get(scenario.category, "kg_query")


def _extract_seed_from_id(scenario_id: str) -> str | None:
    """Scenario IDs follow case-<category>-<num>-<intervention>-<outcome>.
    Token [3] is the intervention seed."""
    parts = scenario_id.split("-")
    if len(parts) < 4 or not parts[3]:
        return None
    return parts[3].replace("_", " ")


def _tokenize_hdi(scenario_id: str, question: str) -> tuple[str, str]:
    """Heuristic herb/drug split from scenario_id or question text.

    Scenario ID convention: case-hdi-NNN-<herb>-<drug>
    Falls back to splitting on common conjunctions in the question.
    """
    parts = scenario_id.split("-")
    # case-hdi-NNN-<herb>-<drug>  → parts[3]=herb, parts[4]=drug
    if len(parts) >= 5 and parts[3] and parts[4]:
        return parts[3].replace("_", " "), parts[4].replace("_", " ")
    # fallback: split on common conjunctions
    for sep in (" + ", " with ", " and "):
        if sep in question.lower():
            left, _, right = question.lower().partition(sep)
            return left.strip(), right.strip()
    return question, ""


def _select_bindings(scenario: Scenario) -> dict[str, Any]:
    """Build the template-binding dict the retrieval plan needs."""
    intent = _select_intent(scenario)
    if intent == "hdi_check":
        herb, drug = _tokenize_hdi(scenario.id, scenario.research_question)
        return {"herb": herb, "drug": drug}
    if intent == "bilingual_term":
        return {"term": _extract_seed_from_id(scenario.id) or scenario.research_question}
    seed = _extract_seed_from_id(scenario.id) or scenario.research_question
    return {"seed": seed, "question": scenario.research_question}


def _chains_to_kg_result(chains: list[dict[str, Any]]) -> KGResult:
    """Convert RetrievalResult.chains (raw MCP responses) into a KGResult.

    Each response in `chains` is a raw dict returned by MCPClient.call_tool():
      - semantic-search returns: {"entities": [{"id": ..., "name": ..., ...}], ...}
      - get-subgraph returns:    {"chains": [{"edges": [{"src_id": ..., "tgt_id": ...,
                                   "rel_type": ..., "source_id": ...,
                                   "evidence_tier": ...}, ...]}, ...], ...}
      - get-entity returns:      {"id": ..., "name": ..., "labels": [...], ...}

    Mapping assumption:
      For get-subgraph responses: each chain's edges map to local KGEdge via
        edge.src_id → KGEdge.src, edge.tgt_id → KGEdge.tgt,
        edge.rel_type → KGEdge.edge, edge.source_id → KGEdge.source_id,
        edge.evidence_tier → KGEdge.evidence_tier (coerced to local Literal),
        weight=1.0 (MCP schema has no weight field).

      For semantic-search/get-entity responses (entity-only): each entity becomes
        a single degenerate ProvenanceChain with one synthetic KGEdge linking
        a "query" sentinel to the entity. This satisfies ProvenanceChain's
        min_length=1 requirement while preserving the retrieved entity for
        downstream calibration.

    If all chains are empty/unparseable, returns a KGResult with chains=[]
    and raw_subgraph_node_count/edge_count=0 (retrieval-was-attempted-empty).
    """
    local_chains: list[ProvenanceChain] = []
    total_edges = 0

    for response in chains:
        if not isinstance(response, dict):
            continue

        # --- get-subgraph responses: carry a "chains" list of typed edges ---
        raw_subgraph_chains = response.get("chains")
        if raw_subgraph_chains and isinstance(raw_subgraph_chains, list):
            for raw_chain in raw_subgraph_chains:
                raw_edges = (
                    raw_chain.get("edges", [])
                    if isinstance(raw_chain, dict)
                    else []
                )
                if not raw_edges:
                    continue
                local_edges: list[KGEdge] = []
                for e in raw_edges:
                    if not isinstance(e, dict):
                        continue
                    raw_tier = e.get("evidence_tier") or "unknown"
                    tier = raw_tier if raw_tier in _LOCAL_EVIDENCE_TIERS else "unknown"
                    local_edges.append(KGEdge(
                        src=str(e.get("src_id") or "unknown"),
                        edge=str(e.get("rel_type") or "UNKNOWN"),
                        tgt=str(e.get("tgt_id") or "unknown"),
                        source_id=str(e.get("source_id") or "mcp:get-subgraph"),
                        weight=1.0,
                        evidence_tier=tier,  # type: ignore[arg-type]
                    ))
                if local_edges:
                    local_chains.append(ProvenanceChain(edges=local_edges))
                    total_edges += len(local_edges)
            continue  # handled as get-subgraph response

        # --- semantic-search / get-entity responses: entity list only ---
        entities = response.get("entities")
        if entities and isinstance(entities, list):
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                entity_id = str(entity.get("id") or entity.get("name") or "unknown")
                if entity_id == "unknown":
                    continue
                # Degenerate single-edge chain: "query" -[RETRIEVED]-> entity_id
                local_chains.append(ProvenanceChain(edges=[KGEdge(
                    src="query",
                    edge="RETRIEVED",
                    tgt=entity_id,
                    source_id="mcp:semantic-search",
                    weight=1.0,
                    evidence_tier="unknown",
                )]))
                total_edges += 1
            continue

        # --- get-entity single-entity response ---
        entity_id = response.get("id")
        if entity_id:
            local_chains.append(ProvenanceChain(edges=[KGEdge(
                src="query",
                edge="RETRIEVED",
                tgt=str(entity_id),
                source_id="mcp:get-entity",
                weight=1.0,
                evidence_tier="unknown",
            )]))
            total_edges += 1

    return KGResult(
        chains=local_chains,
        raw_subgraph_node_count=0,
        raw_subgraph_edge_count=total_edges,
        query_mode="hybrid",
    )


def run(scenario: Scenario) -> ResearchSynthesis:
    """Wrap run_case_study for benchmarking.

    Pre-fetches KG retrieval via the new kg-mcp tool surface (semantic-search,
    get-subgraph, get-entity), then delegates the AG2 multi-agent panel to
    run_case_study via the new preset_kg= parameter. Braintrust span IDs from
    every tool call are threaded onto ResearchSynthesis.bt_span_ids for §A.3
    provenance citations.
    """
    mcp = build_mcp_client()
    _ = build_cerebras_client()  # ensure LLM creds resolved at this layer; AG2 panel uses its own factory
    executor = RetrievalExecutor(mcp_client=mcp)

    intent = _select_intent(scenario)
    plan = RETRIEVAL_PLAN_BY_INTENT[intent]
    bindings = _select_bindings(scenario)
    retrieval = executor.execute(plan, bindings)

    preset_kg = _chains_to_kg_result(retrieval.chains)

    rq, triage = _scenario_to_preset(scenario)
    spec = {
        "id": scenario.id,
        "research_question": scenario.research_question,
        "category": scenario.category,
        "version": scenario.version,
    }

    with tempfile.TemporaryDirectory(prefix="diet_os_eval_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        spec_path = tmp_path / f"{scenario.id}.json"
        spec_path.write_text(json.dumps(spec, indent=2))
        out_dir = tmp_path / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        synthesis = run_case_study(
            spec_path, out_dir,
            preset_question=rq, preset_triage=triage,
            preset_kg=preset_kg,
        )

    synthesis.bt_span_ids = retrieval.bt_span_ids
    return synthesis
