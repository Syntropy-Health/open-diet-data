"""Baseline registry for DietResearchBench-Clinical evaluation.

Each baseline implements the shared contract:
    run(scenario: Scenario) -> ResearchSynthesis

The BASELINES dict maps system name → run function for use by the eval runner.
"""
from typing import Callable

from agents.models import ResearchSynthesis  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]

from eval.baselines.single_llm import run as single_llm
from eval.baselines.single_llm_rag import run as single_llm_rag
from eval.baselines.yang2025 import run as yang2025
from eval.baselines.medagents import run as medagents
from eval.baselines.mdagents import run as mdagents
from eval.baselines.diet_os import run as diet_os

BASELINES: dict[str, Callable[[Scenario], ResearchSynthesis]] = {
    "single_llm": single_llm,
    "single_llm_rag": single_llm_rag,
    "yang2025": yang2025,
    "medagents": medagents,
    "mdagents": mdagents,
    "diet_os": diet_os,
}

__all__ = ["BASELINES"]
