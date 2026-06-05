# shrine-diet-bioactivity/agents/tests/test_assembly.py
import pytest
from autogen import ConversableAgent, GroupChat, GroupChatManager

from agents.panel.assembly import assemble_panel  # type: ignore[import-not-found]
from agents.models import Triage

pytestmark = [pytest.mark.unit]


def test_assemble_panel_low_complexity_returns_dietitian_plus_safety():
    triage = Triage(complexity="low", rationale="single intervention", red_flags=[])
    chat, manager = assemble_panel(triage)
    assert isinstance(chat, GroupChat)
    assert isinstance(manager, GroupChatManager)
    # Minimum viable panel is 2 agents — AG2 GroupChat rejects a solo chat.
    # Dietitian + SafetyReviewer: every low-complexity rec gets a safety check.
    role_names = sorted(a.name for a in chat.agents)
    assert role_names == sorted(["Dietitian", "SafetyReviewer"])


def test_assemble_panel_moderate_returns_three_role_team():
    triage = Triage(complexity="moderate", rationale="multi-drug", red_flags=["polypharmacy_3plus"])
    chat, manager = assemble_panel(triage)
    role_names = sorted(a.name for a in chat.agents)
    assert role_names == sorted(["Dietitian", "Pharmacologist", "TCMPractitioner"])


def test_assemble_panel_high_returns_full_six():
    triage = Triage(complexity="high", rationale="pregnancy + weak-evidence", red_flags=["pregnancy"])
    chat, manager = assemble_panel(triage)
    assert len(chat.agents) == 6
    # max_round = 2*N+2 so every role gets a turn even when the verbose
    # zai-glm-4.7 model causes the Moderator (GroupChatManager) to consume
    # extra turns in the round-robin. The old `len(roles)` caused ~1 verdict
    # per 40-scenario run because moderator turns exhausted the budget.
    assert chat.max_round == 2 * len(chat.agents) + 2
