import pytest

pytestmark = [pytest.mark.unit]


def test_diet_to_compounds_maps_to_semantic_search_plus_get_subgraph():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    plan = RETRIEVAL_PLAN_BY_INTENT["diet_to_compounds"]
    assert plan[0]["tool"] == "semantic-search"
    assert plan[1]["tool"] == "get-subgraph"
    assert plan[1]["depth"] == 2


def test_hdi_check_maps_to_two_entity_resolutions_plus_subgraph_join():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    plan = RETRIEVAL_PLAN_BY_INTENT["hdi_check"]
    assert plan[0]["tool"] == "semantic-search"
    assert plan[1]["tool"] == "semantic-search"
    assert plan[2]["tool"] == "get-subgraph"
    assert plan[2]["start_from_intersection"] is True


def test_bilingual_term_maps_to_semantic_search_with_lang_filter():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    plan = RETRIEVAL_PLAN_BY_INTENT["bilingual_term"]
    assert plan[0]["tool"] == "semantic-search"
    assert plan[0]["lang_filter"] in ("zh", "en", "auto")


def test_all_v1_intents_have_a_plan():
    from eval.baselines.tool_mapping import RETRIEVAL_PLAN_BY_INTENT  # type: ignore[import-not-found]
    v1_intents = {
        "kg_query", "diet_to_compounds", "compound_to_targets",
        "compound_to_diseases", "herb_to_diseases", "herb_to_symptoms",
        "compound_to_symptoms", "hdi_check", "bilingual_term",
        "node_neighborhood",
    }
    assert v1_intents.issubset(set(RETRIEVAL_PLAN_BY_INTENT.keys()))
