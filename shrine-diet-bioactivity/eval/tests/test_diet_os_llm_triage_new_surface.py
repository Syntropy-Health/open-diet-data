"""Tests for the refactored diet_os_llm_triage.py — new kg-mcp tool surface,
bt_span_ids threading, and the LLM-triage ablation invariant.

Three unit tests covering:
1. Correct retrieval plan is invoked (hdi_check for multi_drug_hdi scenarios).
2. bt_span_ids are threaded onto the returned ResearchSynthesis in order.
3. run_case_study is called WITHOUT preset_question/preset_triage (ablation invariant).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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

def test_diet_os_llm_triage_calls_hdi_check_plan_for_hdi_scenarios(hdi_scenario: Scenario):
    """diet_os_llm_triage must select the hdi_check retrieval plan for multi_drug_hdi.

    Mirrors the equivalent test in test_diet_os_new_surface.py. The ablation
    uses the same retrieval surface; only triage differs.
    """
    from eval.baselines.retrieval_executor import RetrievalResult  # type: ignore[import-not-found]
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]

    hdi_plan = RETRIEVAL_PLAN_BY_INTENT["hdi_check"]

    fake_result = RetrievalResult(
        chains=[
            {"entities": [{"id": "herb:stjohnswort"}], "_bt_span_id": "s1"},
            {"entities": [{"id": "compound:warfarin"}], "_bt_span_id": "s2"},
            {"chains": [], "_bt_span_id": "s3"},
        ],
        bt_span_ids=["s1", "s2", "s3"],
    )

    captured_plan: list = []

    def _capture_execute(plan, bindings):
        captured_plan.extend(plan)
        return fake_result

    stub = _stub_synthesis(hdi_scenario.research_question)
    fake_mcp = MagicMock()

    with patch("eval.baselines.diet_os_llm_triage.build_mcp_client", return_value=fake_mcp), \
         patch("eval.baselines.diet_os_llm_triage.build_cerebras_client", return_value=MagicMock()), \
         patch("eval.baselines.diet_os_llm_triage.RetrievalExecutor") as MockExecutor, \
         patch("eval.baselines.diet_os_llm_triage.run_case_study", return_value=stub):
        MockExecutor.return_value.execute.side_effect = _capture_execute
        import eval.baselines.diet_os_llm_triage as mod  # type: ignore[import-not-found]
        mod.run(hdi_scenario)

    assert len(captured_plan) == len(hdi_plan), (
        f"expected {len(hdi_plan)} plan steps, got {len(captured_plan)}"
    )
    tool_calls_in_plan = [step["tool"] for step in captured_plan]
    assert tool_calls_in_plan[0] == "semantic-search", (
        f"first plan step must be semantic-search; got {tool_calls_in_plan[0]!r}"
    )
    assert "get-subgraph" in tool_calls_in_plan, (
        f"get-subgraph must appear in plan; got {tool_calls_in_plan}"
    )


# ---------------------------------------------------------------------------
# Test 2 — bt_span_ids are threaded onto synthesis in order
# ---------------------------------------------------------------------------

def test_diet_os_llm_triage_threads_bt_span_ids(herbal_scenario: Scenario):
    """bt_span_ids from each MCP tool call must be appended to synthesis.bt_span_ids
    in the order the calls were made.

    This test also confirms the ablation pipeline records provenance via the
    new kg-mcp tool surface (mirrors the Task 9 test for diet_os).
    """
    responses = [
        {"entities": [{"id": "herb:ginger"}], "_bt_span_id": "s1"},
        {"chains": [], "_bt_span_id": "s2"},
    ]
    fake_mcp = _make_fake_mcp(responses)
    stub = _stub_synthesis(herbal_scenario.research_question)

    with patch("eval.baselines.diet_os_llm_triage.build_mcp_client", return_value=fake_mcp), \
         patch("eval.baselines.diet_os_llm_triage.build_cerebras_client", return_value=MagicMock()), \
         patch("eval.baselines.diet_os_llm_triage.run_case_study", return_value=stub):
        import eval.baselines.diet_os_llm_triage as mod  # type: ignore[import-not-found]
        result = mod.run(herbal_scenario)

    assert result.bt_span_ids == ["s1", "s2"], (
        f"bt_span_ids must be ordered and complete; got {result.bt_span_ids}"
    )


# ---------------------------------------------------------------------------
# Test 3 — ablation invariant: run_case_study NOT called with preset_question/preset_triage
# ---------------------------------------------------------------------------

def test_diet_os_llm_triage_threads_bt_span_ids_no_preset_triage(herbal_scenario: Scenario):
    """Ablation invariant safety net: run_case_study must NOT receive preset_question
    or preset_triage kwargs. Only preset_kg is passed (new kg-mcp retrieval).

    This is the key difference from diet_os (which passes all three presets).
    Violating this invariant would collapse the ablation into diet_os and
    invalidate §6.5 of the paper.
    """
    responses = [
        {"entities": [{"id": "herb:ginger", "name": "Ginger"}], "_bt_span_id": "s1"},
        {
            "chains": [{"edges": [{"src_id": "ginger", "tgt_id": "nausea",
                                   "rel_type": "TREATS", "source_id": "duke:1",
                                   "evidence_tier": "clinical_trial"}]}],
            "_bt_span_id": "s2",
        },
    ]
    fake_mcp = _make_fake_mcp(responses)
    stub = _stub_synthesis(herbal_scenario.research_question)

    captured_kwargs: dict = {}

    def _capture_run_case_study(*args, **kwargs) -> ResearchSynthesis:
        captured_kwargs.update(kwargs)
        return stub

    with patch("eval.baselines.diet_os_llm_triage.build_mcp_client", return_value=fake_mcp), \
         patch("eval.baselines.diet_os_llm_triage.build_cerebras_client", return_value=MagicMock()), \
         patch("eval.baselines.diet_os_llm_triage.run_case_study",
               side_effect=_capture_run_case_study):
        import eval.baselines.diet_os_llm_triage as mod  # type: ignore[import-not-found]
        result = mod.run(herbal_scenario)

    # --- ablation invariant: no gold-preset triage injected ---
    assert captured_kwargs.get("preset_question") is None, (
        "diet_os_llm_triage must NOT pass preset_question to run_case_study "
        "(ablation invariant: triage must be LLM-emitted)"
    )
    assert captured_kwargs.get("preset_triage") is None, (
        "diet_os_llm_triage must NOT pass preset_triage to run_case_study "
        "(ablation invariant: triage must be LLM-emitted)"
    )

    # --- new surface: preset_kg must be passed and be a KGResult ---
    assert "preset_kg" in captured_kwargs, "run_case_study must receive preset_kg kwarg"
    assert isinstance(captured_kwargs["preset_kg"], KGResult), (
        f"preset_kg must be a KGResult; got {type(captured_kwargs['preset_kg'])}"
    )

    # --- provenance: bt_span_ids threaded ---
    assert result.bt_span_ids == ["s1", "s2"], (
        f"bt_span_ids must be threaded from retrieval; got {result.bt_span_ids}"
    )
