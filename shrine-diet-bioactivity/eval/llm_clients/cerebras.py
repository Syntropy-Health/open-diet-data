"""Cerebras Inference client wrapper for gpt-oss-120b.

Cerebras exposes an OpenAI-SDK-compatible HTTP API at
https://api.cerebras.ai/v1. Free tier: 1M tokens/day. Replaces the
v1 paper's OpenRouter Nemotron client; preserves the "free-tier
constrained-inference" framing while moving to a materially more
capable model.

Model substitution note: the original plan specified Qwen-3-235B-Instruct,
but Cerebras free tier (as of 2026-06-04) only serves zai-glm-4.7 and
gpt-oss-120b. We first tried zai-glm-4.7 but it is a reasoning model that
spends ~3000 reasoning tokens/call (returning content=None when max_tokens
is too small) and its ~5k tokens/call blows the 1M-tokens/day free cap over
a ~880-call matrix. gpt-oss-120b (OpenAI open-weight 120B MoE) at
reasoning_effort=low uses ~330 tokens/call, commits to verdicts, and fits
the daily budget. reasoning_effort=low is injected globally for gpt-oss
models by eval.llm_clients.rate_limit.
"""
from __future__ import annotations

import os
from openai import OpenAI

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_DEFAULT_MODEL = "gpt-oss-120b"


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
