"""Tests for citation_faithfulness and citation_fabrication_rate metrics.

These measure the hallucinated-provenance failure mode: panel agents cite
candidate_chains indices that don't exist (e.g. case-hdi-005-ginkgo-aspirin
cites [101, 112] into an empty chain list).

Distinct from provenance_faithfulness (edge round-trip via Cypher): these
functions operate on RoleVerdict.cited_chains index lists only.
"""
from __future__ import annotations

import math

import pytest

from agents.models import (  # type: ignore[import-not-found]
    ConfidenceComponents,
    KGEdge,
    PanelDeliberation,
    ProvenanceChain,
    ResearchQuestion,
    ResearchSynthesis,
    RoleVerdict,
    Triage,
)
from eval.metrics import (  # type: ignore[import-not-found]
    citation_fabrication_rate,
    citation_faithfulness,
)

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------

_EDGE = KGEdge(
    src="HerbA",
    edge="CONTAINS_COMPOUND",
    tgt="CompoundX",
    source_id="duke:1",
    weight=0.9,
    evidence_tier="experimental",
)

_CHAIN = ProvenanceChain(edges=[_EDGE])


def _make_chain() -> ProvenanceChain:
    return ProvenanceChain(edges=[_EDGE])


def _make_verdict(cited: list[int]) -> RoleVerdict:
    return RoleVerdict(
        role="Pharmacologist",
        verdict="caution",
        support=[],
        concerns=[],
        notes="",
        cited_chains=cited,
    )


def _make_synthesis(
    n_chains: int,
    verdicts: list[RoleVerdict],
) -> ResearchSynthesis:
    """Build a minimal ResearchSynthesis with n_chains candidate chains."""
    return ResearchSynthesis(
        question=ResearchQuestion(text="test question"),
        triage=Triage(complexity="low", rationale="test", red_flags=[]),
        candidate_chains=[_make_chain() for _ in range(n_chains)],
        panel=PanelDeliberation(
            verdicts=verdicts,
            dissent=[],
            moderator_summary="test",
        ),
        confidence=0.5,
        components=ConfidenceComponents(
            evidence_tier=0.5, hdi_risk=0.0, question_fit=0.5
        ),
        defer_to_clinician=False,
    )


# ---------------------------------------------------------------------------
# Test 1: all citations faithful
# ---------------------------------------------------------------------------


def test_all_citations_faithful() -> None:
    """1 prediction with 3 chains, verdict cites [0, 1, 2] — all faithful."""
    pred = _make_synthesis(
        n_chains=3,
        verdicts=[_make_verdict([0, 1, 2])],
    )
    assert citation_faithfulness([pred]) == 1.0
    assert citation_fabrication_rate([pred]) == 0.0


# ---------------------------------------------------------------------------
# Test 2: fabricated citations when candidate_chains is empty (ginkgo case)
# ---------------------------------------------------------------------------


def test_fabricated_when_chains_empty() -> None:
    """candidate_chains=[], verdict cites [101, 112] — both fabricated.

    Mirrors case-hdi-005-ginkgo-aspirin: Pharmacologist cited_chains=[101, 112]
    against an empty candidate_chains list.
    """
    pred = _make_synthesis(
        n_chains=0,
        verdicts=[_make_verdict([101, 112])],
    )
    assert citation_faithfulness([pred]) == 0.0
    assert citation_fabrication_rate([pred]) == 1.0


# ---------------------------------------------------------------------------
# Test 3: mixed micro-average
# ---------------------------------------------------------------------------


def test_mixed_micro_average() -> None:
    """pred A: 3 chains, cites [0,1] (2 faithful); pred B: 0 chains, cites [5] (1 fabricated).

    citation_faithfulness = 2/3 ≈ 0.6667.
    fabrication_rate = 1/2 = 0.5 (pred B fabricates, pred A does not).
    """
    pred_a = _make_synthesis(n_chains=3, verdicts=[_make_verdict([0, 1])])
    pred_b = _make_synthesis(n_chains=0, verdicts=[_make_verdict([5])])

    faith = citation_faithfulness([pred_a, pred_b])
    assert abs(faith - 2 / 3) < 1e-9

    fab = citation_fabrication_rate([pred_a, pred_b])
    assert abs(fab - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# Test 4: out-of-range index counts as fabricated
# ---------------------------------------------------------------------------


def test_out_of_range_index_counts_as_fabricated() -> None:
    """candidate_chains length 2, verdict cites [0, 5].

    Index 0 is faithful; index 5 is out of range.
    citation_faithfulness = 1/2 = 0.5.
    fabrication_rate = 1/1 = 1.0 (the single prediction fabricates).
    """
    pred = _make_synthesis(
        n_chains=2,
        verdicts=[_make_verdict([0, 5])],
    )
    assert abs(citation_faithfulness([pred]) - 0.5) < 1e-9
    assert citation_fabrication_rate([pred]) == 1.0


# ---------------------------------------------------------------------------
# Test 5: NaN when no citations at all
# ---------------------------------------------------------------------------


def test_faithfulness_nan_when_no_citations() -> None:
    """Predictions with empty cited_chains everywhere → citation_faithfulness is nan."""
    pred_a = _make_synthesis(n_chains=3, verdicts=[_make_verdict([])])
    pred_b = _make_synthesis(n_chains=0, verdicts=[_make_verdict([])])
    result = citation_faithfulness([pred_a, pred_b])
    assert math.isnan(result)


# ---------------------------------------------------------------------------
# Test 6: fabrication rate zero when all citations faithful or uncited
# ---------------------------------------------------------------------------


def test_fabrication_rate_zero_when_all_faithful_or_uncited() -> None:
    """Mix of faithful citations and uncited predictions → fabrication_rate 0.0."""
    pred_faithful = _make_synthesis(
        n_chains=3,
        verdicts=[_make_verdict([0, 1, 2])],
    )
    pred_uncited = _make_synthesis(
        n_chains=5,
        verdicts=[_make_verdict([])],
    )
    assert citation_fabrication_rate([pred_faithful, pred_uncited]) == 0.0


# ---------------------------------------------------------------------------
# Test 7: prediction with no citations does not count as fabricating
# ---------------------------------------------------------------------------


def test_prediction_with_no_citations_does_not_fabricate() -> None:
    """candidate_chains=[], but no verdict cites anything → fabrication_rate 0.0.

    Empty cited_chains is NOT a fabrication — the agent simply did not cite.
    Only citing an out-of-range index is fabrication.
    """
    pred = _make_synthesis(
        n_chains=0,
        verdicts=[_make_verdict([])],
    )
    assert citation_fabrication_rate([pred]) == 0.0
    # faithfulness is nan (no citations to judge)
    assert math.isnan(citation_faithfulness([pred]))
