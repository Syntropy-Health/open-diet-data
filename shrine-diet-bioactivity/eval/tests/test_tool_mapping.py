import pytest

pytestmark = [pytest.mark.unit]


def test_diet_to_compounds_maps_to_v1_diet_to_compounds():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    plan = RETRIEVAL_PLAN_BY_INTENT["diet_to_compounds"]
    assert plan[0]["tool"] == "kg_diet_to_compounds"
    assert "seed" in plan[0]["args"]


def test_hdi_check_maps_to_v1_hdi_check():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    plan = RETRIEVAL_PLAN_BY_INTENT["hdi_check"]
    assert plan[0]["tool"] == "kg_hdi_check"
    assert "herb" in plan[0]["args"]
    assert "drug" in plan[0]["args"]


def test_bilingual_term_maps_to_v1_bilingual_term():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    plan = RETRIEVAL_PLAN_BY_INTENT["bilingual_term"]
    assert plan[0]["tool"] == "kg_bilingual_term"
    assert "term" in plan[0]["args"]


def test_all_v1_intents_have_a_plan():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    v1_intents = {
        "kg_query", "diet_to_compounds", "compound_to_targets",
        "compound_to_diseases", "herb_to_diseases", "herb_to_symptoms",
        "compound_to_symptoms", "hdi_check", "bilingual_term",
        "node_neighborhood",
    }
    assert v1_intents.issubset(set(RETRIEVAL_PLAN_BY_INTENT.keys()))
