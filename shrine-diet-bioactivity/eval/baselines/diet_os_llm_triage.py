"""Diet-OS LLM-Triage ablation baseline — same panel + new kg-mcp retrieval as
`diet_os`, but with LLM-emitted Triage instead of gold-preset Triage.

Ablation contract (paper §6.5):
  This cell isolates the Triage step as the sole varying factor vs `diet_os`.
  The canonical `diet_os` uses `scenario.gold.expected_complexity` to pre-set
  the `Triage` object, giving it gold-derived complexity. Here, `preset_triage`
  is intentionally NOT passed to `run_case_study`; the triage agent runs at
  runtime and emits its own complexity/PICO judgement.

  Comparing diet_os vs diet_os_llm_triage answers: does the architectural lift
  (KG-grounded retrieval bundle + role-priored panel) survive when triage is
  also LLM-emitted?

Retrieval surface (v2 — post-Task-9):
  Pre-fetches KG retrieval via the new kg-mcp tool surface (semantic-search,
  get-subgraph, get-entity) through eval.mcp_clients.MCPClient, then passes
  the result to run_case_study via preset_kg=. Every MCP call emits a
  Braintrust span; span IDs are collected and threaded onto the returned
  ResearchSynthesis as .bt_span_ids[] for §A.3 provenance citations.

LLM-triage model (v2):
  Triage now runs on Cerebras Qwen-3-235B (replacing v1 paper's free-tier
  Nemotron which had 33/40 JSON parse failures). The ablation contract is
  preserved: this baseline differs from `diet_os` ONLY in whether Triage is
  gold-preset vs LLM-emitted.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agents.models import ResearchSynthesis  # type: ignore[import-not-found]
from agents.run_case_study import run_case_study  # type: ignore[import-not-found]
from eval.baselines.diet_os import (  # type: ignore[import-not-found]
    _chains_to_kg_result,
    _select_bindings,
    _select_intent,
)
from eval.baselines.retrieval_executor import RetrievalExecutor  # type: ignore[import-not-found]
from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
from eval.llm_clients.cerebras import build_cerebras_client  # type: ignore[import-not-found]
from eval.mcp_clients import build_mcp_client  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]


def run(scenario: Scenario) -> ResearchSynthesis:
    """Run the AG2 multi-agent panel with kg-mcp retrieval but LLM-emitted Triage.

    Pre-fetches KG retrieval via the new kg-mcp tool surface (semantic-search,
    get-subgraph, get-entity), passes the result to run_case_study via
    preset_kg=, and threads Braintrust span IDs onto the returned
    ResearchSynthesis.

    Critical: preset_question and preset_triage are intentionally NOT passed.
    The triage agent runs at runtime — this is the ablation variable.
    """
    mcp = build_mcp_client()
    _ = build_cerebras_client()  # ensure LLM creds resolved early; AG2 panel uses its own factory
    executor = RetrievalExecutor(mcp_client=mcp)

    intent = _select_intent(scenario)
    plan = RETRIEVAL_PLAN_BY_INTENT[intent]
    bindings = _select_bindings(scenario)
    retrieval = executor.execute(plan, bindings)
    preset_kg = _chains_to_kg_result(retrieval.chains)

    spec = {
        "id": scenario.id,
        "research_question": scenario.research_question,
        "category": scenario.category,
        "version": scenario.version,
    }

    with tempfile.TemporaryDirectory(prefix="diet_os_llm_triage_eval_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        spec_path = tmp_path / f"{scenario.id}.json"
        spec_path.write_text(json.dumps(spec, indent=2))
        out_dir = tmp_path / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Critical: do NOT pass preset_question + preset_triage —
        # this baseline is the LLM-triage ablation. The triage agent
        # runs at runtime against the (now Cerebras Qwen-3-235B) LLM.
        synthesis = run_case_study(
            spec_path, out_dir,
            preset_kg=preset_kg,
        )

    synthesis.bt_span_ids = retrieval.bt_span_ids
    return synthesis
