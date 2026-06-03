"""Cerebras Inference client wrapper for Qwen-3-235B-Instruct.

Cerebras exposes an OpenAI-SDK-compatible HTTP API at
https://api.cerebras.ai/v1. Free tier: 1M tokens/day. Replaces the
v1 paper's OpenRouter Nemotron client; preserves the "free-tier
constrained-inference" framing while moving to a materially more
capable model.
"""
from __future__ import annotations

import os
from openai import OpenAI

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_DEFAULT_MODEL = "qwen-3-235b-instruct"


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
    return OpenAI(api_key=api_key, base_url=CEREBRAS_BASE_URL)
