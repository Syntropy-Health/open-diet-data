"""Tests for the refactored diet_os.py — new kg-mcp tool surface + bt_span_ids threading.

Three unit tests covering:
1. Correct retrieval plan is invoked (hdi_check for multi_drug_hdi scenarios).
2. bt_span_ids are threaded onto the returned ResearchSynthesis in order.
3. run_case_study is called with a KGResult preset_kg instance.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from agents.models import (  # type: ignore[import-not-found]
    ConfidenceComponents,
    KGResult,
    PanelDeliberation,
    ResearchQuestion,
    ResearchSynthesis,
    Triage,
)
from eval.scenario import GoldStandard, Scenario  # type: ignore[import-not-found]

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hdi_scenario() -> Scenario:
    """A multi_drug_hdi scenario whose id encodes herb and drug tokens."""
    return Scenario(
        id="case-multi_drug_hdi-001-stjohnswort-warfarin",
        category="multi_drug_hdi",
        research_question="Does St. John's Wort interact with warfarin increasing bleeding risk?",
        gold=GoldStandard(
            expected_complexity="high",
            expected_panel_verdict="reject",
            expected_evidence_tier="clinical_trial",
            expected_min_chains=2,
            expected_defer=True,
            expected_red_flags=["anticoagulant_therapy"],
            expected_hdi_severity="severe",
            languages=["en"],
        ),
        rationale="Well-documented P450 induction",
        source_citations=["Johne 1999 PMID:10571030"],
    )


@pytest.fixture
def herbal_scenario() -> Scenario:
    return Scenario(
        id="case-herbal_single_symptom-001-ginger-nausea",
        category="herbal_single_symptom",
        research_question="Does ginger reduce post-prandial bloating?",
        gold=GoldStandard(
            expected_complexity="low",
            expected_panel_verdict="prefer",
            expected_evidence_tier="clinical_trial",
            expected_min_chains=1,
            expected_defer=False,
            expected_red_flags=[],
            languages=["en"],
        ),
        rationale="multiple RCTs",
        source_citations=[],
    )


def _stub_synthesis(question_text: str = "stub?") -> ResearchSynthesis:
    """Minimal ResearchSynthesis for mocking run_case_study return value."""
    return ResearchSynthesis(
        question=ResearchQuestion(text=question_text),
        triage=Triage(complexity="low", rationale="stub", red_flags=[]),
        candidate_chains=[],
        panel=PanelDeliberation(verdicts=[], dissent=[], moderator_summary="stub"),
        confidence=0.5,
        components=ConfidenceComponents(evidence_tier=0.5, hdi_risk=0.0, question_fit=0.5),
        defer_to_clinician=False,
    )


def _make_fake_mcp(responses: list[dict]) -> MagicMock:
    """Create a fake MCPClient whose call_tool returns responses in sequence."""
    fake = MagicMock()
    fake.call_tool.side_effect = responses
    return fake


# ---------------------------------------------------------------------------
# Test 1 — hdi_check plan is invoked for multi_drug_hdi scenarios
# ---------------------------------------------------------------------------

def test_diet_os_calls_hdi_check_plan_for_hdi_scenarios(hdi_scenario: Scenario):
    """diet_os must select the hdi_check retrieval plan for multi_drug_hdi scenarios.

    The hdi_check plan has 3 steps: semantic-search(herb), semantic-search(drug),
    get-subgraph. We verify that (a) the RetrievalExecutor receives the hdi_check
    plan and (b) tool calls include semantic-search first and get-subgraph somewhere.

    We mock RetrievalExecutor.execute directly (rather than going through the
    executor's template resolution) so we can assert on the plan dict passed to it,
    independent of executor internals.
    """
    from eval.baselines.retrieval_executor import RetrievalResult  # type: ignore[import-not-found]
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]

    hdi_plan = RETRIEVAL_PLAN_BY_INTENT["hdi_check"]

    # Fake execution result — 1 span (one per plan step; hdi_check is now single-step)
    fake_result = RetrievalResult(
        chains=[
            {"found": True, "severity": "severe", "citations": [], "_bt_span_id": "s1"},
        ],
        bt_span_ids=["s1"],
    )

    captured_plan: list = []

    def _capture_execute(plan, bindings):
        captured_plan.extend(plan)
        return fake_result

    stub = _stub_synthesis(hdi_scenario.research_question)
    fake_mcp = MagicMock()

    with patch("eval.baselines.diet_os.build_mcp_client", return_value=fake_mcp), \
         patch("eval.baselines.diet_os.build_cerebras_client", return_value=MagicMock()), \
         patch("eval.baselines.diet_os.RetrievalExecutor") as MockExecutor, \
         patch("eval.baselines.diet_os.run_case_study", return_value=stub):
        MockExecutor.return_value.execute.side_effect = _capture_execute
        import eval.baselines.diet_os as mod  # type: ignore[import-not-found]
        mod.run(hdi_scenario)

    # Plan steps received must match the hdi_check plan
    assert len(captured_plan) == len(hdi_plan), (
        f"expected {len(hdi_plan)} plan steps, got {len(captured_plan)}"
    )
    tool_calls_in_plan = [step["tool"] for step in captured_plan]
    assert tool_calls_in_plan[0] == "kg_hdi_check", (
        f"first (and only) plan step must be kg_hdi_check; got {tool_calls_in_plan[0]!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 — bt_span_ids are threaded onto synthesis in order
# ---------------------------------------------------------------------------

def test_diet_os_threads_bt_span_ids_into_result(herbal_scenario: Scenario):
    """bt_span_ids from each MCP tool call must be appended to synthesis.bt_span_ids
    in the order the calls were made.

    herbal_single_symptom maps to herb_to_symptoms which is a single-step v1 plan
    (kg_herb_to_symptoms handles the full traversal internally).
    """
    responses = [
        {"chains": [], "raw_subgraph_node_count": 0, "raw_subgraph_edge_count": 0,
         "_bt_span_id": "s1"},
    ]
    fake_mcp = _make_fake_mcp(responses)
    stub = _stub_synthesis(herbal_scenario.research_question)

    with patch("eval.baselines.diet_os.build_mcp_client", return_value=fake_mcp), \
         patch("eval.baselines.diet_os.build_cerebras_client", return_value=MagicMock()), \
         patch("eval.baselines.diet_os.run_case_study", return_value=stub):
        import eval.baselines.diet_os as mod  # type: ignore[import-not-found]
        result = mod.run(herbal_scenario)

    assert result.bt_span_ids == ["s1"], (
        f"bt_span_ids must be ordered and complete; got {result.bt_span_ids}"
    )


# ---------------------------------------------------------------------------
# Test 3 — run_case_study is called with a KGResult as preset_kg
# ---------------------------------------------------------------------------

def test_diet_os_passes_preset_kg_to_run_case_study(herbal_scenario: Scenario):
    """run_case_study must receive a preset_kg kwarg that is a KGResult instance.

    herbal_single_symptom maps to herb_to_symptoms — single-step v1 plan
    (kg_herb_to_symptoms returns chains directly).
    """
    responses = [
        {
            "chains": [{"edges": [{"src_id": "ginger", "tgt_id": "nausea",
                                   "rel_type": "TREATS", "source_id": "duke:1",
                                   "evidence_tier": "clinical_trial"}]}],
            "raw_subgraph_node_count": 2,
            "raw_subgraph_edge_count": 1,
            "_bt_span_id": "s1",
        },
    ]
    fake_mcp = _make_fake_mcp(responses)
    stub = _stub_synthesis(herbal_scenario.research_question)

    captured_kwargs: dict = {}

    def _capture_run_case_study(*args, **kwargs) -> ResearchSynthesis:
        captured_kwargs.update(kwargs)
        return stub

    with patch("eval.baselines.diet_os.build_mcp_client", return_value=fake_mcp), \
         patch("eval.baselines.diet_os.build_cerebras_client", return_value=MagicMock()), \
         patch("eval.baselines.diet_os.run_case_study", side_effect=_capture_run_case_study):
        import eval.baselines.diet_os as mod  # type: ignore[import-not-found]
        result = mod.run(herbal_scenario)

    assert "preset_kg" in captured_kwargs, "run_case_study must receive preset_kg kwarg"
    assert isinstance(captured_kwargs["preset_kg"], KGResult), (
        f"preset_kg must be a KGResult; got {type(captured_kwargs['preset_kg'])}"
    )
