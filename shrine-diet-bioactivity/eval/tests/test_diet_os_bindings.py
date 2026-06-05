"""Unit tests for diet_os canonical-seed extraction (Fix 3).

The KG is keyed by Latin binomial (e.g. 'Zingiber officinale') rather than
the short id token ('ginger'). These tests verify that _extract_canonical_seed
and the _select_bindings helpers prefer the parenthetical binomial from the
research_question text.
"""
import types

import pytest

pytestmark = [pytest.mark.unit]


def test_extracts_binomial_from_parenthetical():
    from eval.baselines.diet_os import _extract_canonical_seed  # type: ignore[import-not-found]

    rq = "does adjunctive ginger (Zingiber officinale) reduce nausea?"
    assert _extract_canonical_seed(rq, "ginger") == "Zingiber officinale"


def test_falls_back_when_no_binomial():
    from eval.baselines.diet_os import _extract_canonical_seed  # type: ignore[import-not-found]

    rq = "does a high-fiber diet relieve constipation?"
    assert _extract_canonical_seed(rq, "fiber") == "fiber"


def test_extracts_multi_word_binomial():
    from eval.baselines.diet_os import _extract_canonical_seed  # type: ignore[import-not-found]

    rq = "Is Hypericum perforatum safe with SSRIs?"
    # no parentheses — falls back
    assert _extract_canonical_seed(rq, "sjw") == "sjw"

    rq2 = "safety of St. John's Wort (Hypericum perforatum) with sertraline"
    assert _extract_canonical_seed(rq2, "sjw") == "Hypericum perforatum"


def test_hdi_terms_prefers_binomial_herb():
    from eval.baselines.diet_os import _extract_hdi_terms_from_question  # type: ignore[import-not-found]

    rq = "safety of adding St. John's Wort (Hypericum perforatum) to sertraline?"
    herb, drug = _extract_hdi_terms_from_question(rq, "case-hdi-001-sjw-sertraline")
    assert herb == "Hypericum perforatum"
    assert drug == "sertraline"


def test_hdi_terms_falls_back_to_id_token_when_no_binomial():
    from eval.baselines.diet_os import _extract_hdi_terms_from_question  # type: ignore[import-not-found]

    rq = "does garlic affect warfarin anticoagulation?"
    herb, drug = _extract_hdi_terms_from_question(rq, "case-hdi-002-garlic-warfarin")
    assert herb == "garlic"
    assert drug == "warfarin"


def test_select_bindings_hdi_uses_question():
    from eval.baselines.diet_os import _select_bindings  # type: ignore[import-not-found]

    # _select_bindings only accesses scenario.id, scenario.category,
    # and scenario.research_question — use SimpleNamespace for speed.
    scenario = types.SimpleNamespace(
        id="case-hdi-001-sjw-sertraline",
        category="multi_drug_hdi",
        research_question=(
            "In a patient stabilised on sertraline 100 mg/day for major depression, "
            "what are the safety implications of adding St. John's Wort "
            "(Hypericum perforatum) for residual mood symptoms?"
        ),
    )
    bindings = _select_bindings(scenario)
    assert bindings["herb"] == "Hypericum perforatum"
    assert bindings["drug"] == "sertraline"


def test_select_bindings_herbal_symptom_uses_binomial():
    from eval.baselines.diet_os import _select_bindings  # type: ignore[import-not-found]

    scenario = types.SimpleNamespace(
        id="case-herbal-001-ginger-nausea",
        category="herbal_single_symptom",
        research_question="does adjunctive ginger (Zingiber officinale) reduce nausea?",
    )
    bindings = _select_bindings(scenario)
    assert bindings["seed"] == "Zingiber officinale"


def test_select_bindings_herbal_symptom_falls_back_to_id():
    from eval.baselines.diet_os import _select_bindings  # type: ignore[import-not-found]

    scenario = types.SimpleNamespace(
        id="case-herbal-002-turmeric-inflammation",
        category="herbal_single_symptom",
        research_question="does turmeric reduce systemic inflammation markers?",
    )
    bindings = _select_bindings(scenario)
    # no parenthetical binomial → falls back to id token
    assert bindings["seed"] == "turmeric"
