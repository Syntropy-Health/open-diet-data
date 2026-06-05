# shrine-diet-bioactivity/agents/panel/assembly.py
"""GroupChat assembly with MDAgents-style adaptive triage.

Maps Triage.complexity → role-agent subset → GroupChat with round-robin
speaker selection + 2-round cap (verdict + rebuttal).

Per-role tool registration (per `staged-mcp-persona-audit.md`):
  Dietitian          → kg_diet_to_compounds, kg_compound_to_symptoms, kg_query
  Pharmacologist     → kg_compound_to_targets, kg_query
  TCMPractitioner    → kg_bilingual_term, kg_herb_to_diseases,
                       kg_herb_to_symptoms, kg_query
  SafetyReviewer     → kg_hdi_check, kg_query
  ClinicalResearch…  → kg_query  (Layer A only — synthesis, not retrieval)
  DeferToClinician   → kg_query

AG2 v0.12.1 inspects function signatures via inject_params + Pydantic's
TypeAdapter. `agents.tools.kg_tools` does NOT use `from __future__ import
annotations` precisely so AG2 can resolve `Literal[...]` and primitive
return types directly. We register kg_tools functions as-is — no thin
wrappers needed — and keep the legacy `_kg_query_tool` shim only for
the kg_query Layer-A fallback that wraps a non-future-annotated module.
"""
from typing import Callable, List, Literal, cast

from autogen import ConversableAgent, GroupChat, GroupChatManager
from autogen.agentchat.agent import Agent

from agents.llm_config import default_llm_config
from agents.models import KGResult, Triage
from agents.panel import (
    build_clinical_research_scientist, build_defer_to_clinician,
    build_dietitian, build_pharmacologist, build_safety_reviewer,
    build_tcm_practitioner,
)
from agents.tools.kg_query import kg_query as _kg_query_impl
from agents.tools.kg_tools import (  # type: ignore[import-not-found]
    kg_bilingual_term, kg_compound_to_symptoms, kg_compound_to_targets,
    kg_diet_to_compounds, kg_hdi_check, kg_herb_to_diseases, kg_herb_to_symptoms,
)


MODERATOR_PROMPT = """\
You are the moderator of a clinical research team. Synthesize the role
verdicts into a PanelDeliberation:
- moderator_summary: 2-3 sentence consensus or majority position.
- dissent: list any minority verdicts the Clinical Research Scientist or
  Safety Reviewer raised — even if the majority disagreed.
- Do NOT over-rule a Safety Reviewer 'reject' verdict. If safety rejects,
  the panel summary must reflect that.
Output a PanelDeliberation JSON.
"""


def _kg_query_tool(
    question: str,
    mode: Literal["local", "global", "hybrid", "naive", "mix"] = "hybrid",
) -> KGResult:
    """Layer-A fallback. Thin wrapper around `agents.tools.kg_query.kg_query`
    that avoids the AG2 v0.12.1 ForwardRef issue with future-annotated
    source modules. Delegates fully to the canonical implementation.
    """
    return _kg_query_impl(question, mode)


# Per-role tool registration map. Each entry is (mcp_name, callable, description).
# kg_query is included as the last fallback for every role.
_KG_QUERY_DESC = "Layer A natural-language Q&A over the KG. Use as last resort when no role-priored tool fits."

ROLE_TOOLS: dict[str, list[tuple[str, Callable, str]]] = {
    "Dietitian": [
        ("kg_diet_to_compounds", kg_diet_to_compounds,
         "Food → bioactive compounds. Seed with a food name (e.g. 'Garlic')."),
        ("kg_compound_to_symptoms", kg_compound_to_symptoms,
         "Compound → herb → symptom (composite). Seed with compound name (e.g. 'CURCUMIN')."),
        ("kg_query", _kg_query_tool, _KG_QUERY_DESC),
    ],
    "Pharmacologist": [
        ("kg_compound_to_targets", kg_compound_to_targets,
         "Compound → protein targets. Seed with compound name (e.g. 'Curcumin' — auto-uppercased)."),
        ("kg_query", _kg_query_tool, _KG_QUERY_DESC),
    ],
    "TCMPractitioner": [
        ("kg_bilingual_term", kg_bilingual_term,
         "Bilingual canonicalization for TCM herb terms. Accepts EN/CN/Pinyin."),
        ("kg_herb_to_diseases", kg_herb_to_diseases,
         "Herb → Disease (CMAUP + HERB 2.0). Seed with Latin name (e.g. 'Ginkgo biloba')."),
        ("kg_herb_to_symptoms", kg_herb_to_symptoms,
         "Herb → Symptom (Duke + SymMap). Seed with herb common or Latin name."),
        ("kg_query", _kg_query_tool, _KG_QUERY_DESC),
    ],
    "SafetyReviewer": [
        ("kg_hdi_check", kg_hdi_check,
         "HDI-Safe-50 lookup. Returns severity + mechanism + citation, or found=false."),
        ("kg_query", _kg_query_tool, _KG_QUERY_DESC),
    ],
    "ClinicalResearchScientist": [
        ("kg_query", _kg_query_tool, _KG_QUERY_DESC),
    ],
    "DeferToClinician": [
        ("kg_query", _kg_query_tool, _KG_QUERY_DESC),
    ],
}


def _select_roles(triage: Triage) -> list[ConversableAgent]:
    if triage.complexity == "low":
        # Minimum viable panel is TWO agents: AG2's GroupChat (round_robin)
        # raises "underpopulated with 1 agents" for a single-member chat.
        # A dietitian + safety reviewer is the smallest defensible clinical
        # panel — every low-complexity recommendation still gets an explicit
        # safety check. (v1 used a lone dietitian, which crashes on the
        # current AG2; this is a disclosed re-run change.)
        return [build_dietitian(), build_safety_reviewer()]
    if triage.complexity == "moderate":
        return [build_dietitian(), build_pharmacologist(), build_tcm_practitioner()]
    return [
        build_dietitian(), build_pharmacologist(), build_tcm_practitioner(),
        build_clinical_research_scientist(), build_safety_reviewer(),
        build_defer_to_clinician(),
    ]


def _register_role_tools(agents: list[ConversableAgent]) -> None:
    """Register per-role tool subsets. Each agent gets the tools listed for
    its role name in ROLE_TOOLS, plus kg_query as a universal fallback.
    Agents with no entry in ROLE_TOOLS get kg_query only.
    """
    for a in agents:
        tools = ROLE_TOOLS.get(a.name, [("kg_query", _kg_query_tool, _KG_QUERY_DESC)])
        for tool_name, fn, description in tools:
            a.register_for_llm(name=tool_name, description=description)(fn)
            a.register_for_execution(name=tool_name)(fn)


def assemble_panel(triage: Triage) -> tuple[GroupChat, GroupChatManager]:
    roles = _select_roles(triage)
    # Tool registration is intentionally skipped: the Option-A pre-fetch path
    # injects KG retrieval into the moderator prompt (run_case_study passes
    # preset_kg), so panel agents never need to call KG tools live. Free-tier
    # models don't reliably emit tool_calls anyway (e2-panel-mcp-wiring-results).
    # Critically, Cerebras gpt-oss-120b rejects `tools` + `response_format`
    # together (400 wrong_api_format), and the role agents need response_format
    # (=RoleVerdict) to emit parseable verdicts — so tools must NOT be registered.
    # _register_role_tools(roles)  # retained for the live-tool path; unused here
    # max_round must cover every selected role plus the Moderator (GroupChatManager)
    # which also consumes turns in the round-robin. zai-glm-4.7 is verbose and the
    # legacy `len(roles)` caused the panel to hit "Maximum rounds reached" after
    # only ~1 role spoke (the Moderator's turns consumed the budget). Give every
    # role a full turn plus headroom for moderator interjections and a closing
    # summary: 2 * len(roles) + 2.
    chat = GroupChat(
        agents=cast(List[Agent], roles),
        messages=[],
        max_round=2 * len(roles) + 2,
        speaker_selection_method="round_robin",       # deterministic, cheap
    )
    manager = GroupChatManager(
        groupchat=chat,
        name="Moderator",
        llm_config=default_llm_config(response_format=None),
        system_message=MODERATOR_PROMPT,
    )
    return chat, manager
