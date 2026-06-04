"""Diet-OS wrapper baseline — pre-fetches retrieval via the deployed kg-mcp
v1 tool surface then runs the AG2 multi-agent panel via run_case_study with
preset_kg.

Retrieval surface: v1 kg-mcp tools (kg_query, kg_hdi_check,
kg_diet_to_compounds, etc.) via eval.mcp_clients.MCPClient. Every call
emits a Braintrust span; span IDs are collected and threaded onto the
returned ResearchSynthesis as .bt_span_ids[] for §A.3 case-study
provenance citations.

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
    """Convert RetrievalResult.chains (raw MCP tool payloads) into a KGResult.

    Each element in `chains` is the parsed payload returned by
    MCPClient.call_tool() after unwrapping the MCP content envelope.
    The v1 kg-mcp gateway returns distinct shapes per tool family:

    Traversal tools (kg_diet_to_compounds, kg_compound_to_targets,
    kg_compound_to_diseases, kg_herb_to_diseases, kg_herb_to_symptoms,
    kg_compound_to_symptoms, kg_node_neighborhood):
      {"chains": [...ProvenanceChain-like dicts...],
       "raw_subgraph_node_count": int, "raw_subgraph_edge_count": int,
       "bt_span_id": str}
      Each chain dict: {"edges": [{"src_id", "tgt_id", "rel_type",
                                    "source_id", "evidence_tier"}, ...]}

    kg_query:
      {"answer": str, "references": [...citation dicts...],
       "scope_filter": str, "bt_span_id": str}
      references are synthesised into degenerate single-edge chains.

    kg_hdi_check:
      {"found": bool, "severity": str, "mechanism_class": str,
       "evidence_tier": str, "citations": [...], "bt_span_id": str}
      citations are synthesised into degenerate single-edge chains.

    kg_bilingual_term:
      {"term": str, "en": str, "cn": str, "pinyin": str, "bt_span_id": str}
      No edges; produces a single degenerate chain pointing at the term.

    Legacy/fallback shapes (semantic-search entity lists, get-entity):
      Still handled for backwards-compatibility with tests that inject
      {"entities": [...]} or {"id": ...} responses directly.

    If no valid ProvenanceChains can be constructed, returns a KGResult
    with chains=[] and counts=0 (retrieval-was-attempted-empty).
    """
    local_chains: list[ProvenanceChain] = []
    total_nodes = 0
    total_edges = 0

    for response in chains:
        if not isinstance(response, dict):
            continue

        # --- Traversal tool responses: carry a "chains" list of typed edges ---
        raw_subgraph_chains = response.get("chains")
        if raw_subgraph_chains is not None and isinstance(raw_subgraph_chains, list):
            # Accumulate node/edge counts from the traversal payload.
            total_nodes += int(response.get("raw_subgraph_node_count") or 0)
            total_edges += int(response.get("raw_subgraph_edge_count") or 0)
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
                        source_id=str(e.get("source_id") or "mcp:traversal"),
                        weight=1.0,
                        evidence_tier=tier,  # type: ignore[arg-type]
                    ))
                if local_edges:
                    local_chains.append(ProvenanceChain(edges=local_edges))
            continue  # handled as traversal response

        # --- kg_query response: answer + references ---
        if "answer" in response and "references" in response:
            references = response.get("references") or []
            if isinstance(references, list):
                for ref in references:
                    if not isinstance(ref, dict):
                        continue
                    ref_id = str(
                        ref.get("id") or ref.get("entity_id")
                        or ref.get("name") or ref.get("title") or "unknown"
                    )
                    if ref_id == "unknown":
                        continue
                    local_chains.append(ProvenanceChain(edges=[KGEdge(
                        src="query",
                        edge="REFERENCED",
                        tgt=ref_id,
                        source_id="mcp:kg_query",
                        weight=1.0,
                        evidence_tier="unknown",
                    )]))
                    total_edges += 1
            continue

        # --- kg_hdi_check response: citations list ---
        if "found" in response and "citations" in response:
            citations = response.get("citations") or []
            raw_tier = response.get("evidence_tier") or "unknown"
            tier = raw_tier if raw_tier in _LOCAL_EVIDENCE_TIERS else "unknown"
            if isinstance(citations, list):
                for cite in citations:
                    cite_id = str(
                        (cite.get("id") or cite.get("pmid") or cite.get("title") or "unknown")
                        if isinstance(cite, dict) else cite or "unknown"
                    )
                    if cite_id == "unknown":
                        continue
                    local_chains.append(ProvenanceChain(edges=[KGEdge(
                        src="query",
                        edge="HDI_EVIDENCE",
                        tgt=cite_id,
                        source_id="mcp:kg_hdi_check",
                        weight=1.0,
                        evidence_tier=tier,  # type: ignore[arg-type]
                    )]))
                    total_edges += 1
            elif not citations:
                # found=True but empty citations — produce one sentinel chain
                severity = str(response.get("severity") or "unknown")
                local_chains.append(ProvenanceChain(edges=[KGEdge(
                    src="query",
                    edge="HDI_EVIDENCE",
                    tgt=f"hdi:severity={severity}",
                    source_id="mcp:kg_hdi_check",
                    weight=1.0,
                    evidence_tier=tier,  # type: ignore[arg-type]
                )]))
                total_edges += 1
            continue

        # --- kg_bilingual_term response ---
        if "en" in response or "cn" in response or "pinyin" in response:
            term_id = str(response.get("en") or response.get("term") or "unknown")
            if term_id != "unknown":
                local_chains.append(ProvenanceChain(edges=[KGEdge(
                    src="query",
                    edge="BILINGUAL_MATCH",
                    tgt=term_id,
                    source_id="mcp:kg_bilingual_term",
                    weight=1.0,
                    evidence_tier="unknown",
                )]))
                total_edges += 1
            continue

        # --- Legacy / fallback: entity list (semantic-search shape) ---
        entities = response.get("entities")
        if entities and isinstance(entities, list):
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                entity_id = str(entity.get("id") or entity.get("name") or "unknown")
                if entity_id == "unknown":
                    continue
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

        # --- Legacy / fallback: get-entity single-entity response ---
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
        raw_subgraph_node_count=total_nodes,
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
