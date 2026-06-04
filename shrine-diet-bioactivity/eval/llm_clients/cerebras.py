"""Cerebras Inference client wrapper for zai-glm-4.7.

Cerebras exposes an OpenAI-SDK-compatible HTTP API at
https://api.cerebras.ai/v1. Free tier: 1M tokens/day. Replaces the
v1 paper's OpenRouter Nemotron client; preserves the "free-tier
constrained-inference" framing while moving to a materially more
capable model.

Model substitution note: the original plan specified Qwen-3-235B-Instruct,
but Cerebras free tier (as of 2026-06-03) only serves zai-glm-4.7 and
gpt-oss-120b. zai-glm-4.7 (Z.ai / ex-ChatGLM team frontier 235B-class
MoE) was chosen for native zh+en coverage needed by multi_drug_hdi and
tcm_bilingual scenarios.
"""
from __future__ import annotations

import os
from openai import OpenAI

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_DEFAULT_MODEL = "zai-glm-4.7"


def build_cerebras_client() -> OpenAI:
    """Construct an OpenAI-SDK client pointed at Cerebras.

    Raises:
        RuntimeError: if CEREBRAS_API_KEY env var is unset.
    """
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "CEREBRAS_API_KEY is unset. Pull from Infisical "
            "/CEREBRAS_API_KEY (project SyntropyHealth App, env prod)."
        )
    from eval.llm_clients.rate_limit import install_global_rate_limit  # type: ignore[import-not-found]
    install_global_rate_limit()
    return OpenAI(api_key=api_key, base_url=CEREBRAS_BASE_URL)
