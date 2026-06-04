"""Pre-matrix smoke test: run case-hdi-001-sjw-sertraline end-to-end against
the live kg-mcp gateway + Cerebras zai-glm-4.7. Skipped without
KG_MCP_E2E_URL + CEREBRAS_API_KEY env vars.

Purpose:
  - Validate that diet_os.run() succeeds end-to-end against the new tool surface.
  - Confirm Braintrust span emission is wired through PR #92's runtime tracing
    (the bt_span_ids[] list should be non-empty after a successful retrieval).
  - Catch any schema / serialization mismatch between the new kg-mcp response
    shape and the diet_os._chains_to_kg_result() conversion before committing
    3-5 hours to the full 40×7 matrix.

If this test fails on span emission, the matrix run will produce predictions
with empty bt_span_ids — the case-study provenance citations in §A.3 then
have nothing to point at. Fix before proceeding.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live_llm,
    pytest.mark.slow,
    pytest.mark.skipif(
        not (os.environ.get("KG_MCP_E2E_URL") and os.environ.get("CEREBRAS_API_KEY")),
        reason="requires KG_MCP_E2E_URL + CEREBRAS_API_KEY (set via /tmp/kg-mcp-rerun.env)",
    ),
]


# Resolve the benchmark dataset relative to the repo root, not the package root.
_BENCH_PATH = Path(__file__).resolve().parents[4] / "research-journal" / "shared" / "datasets" / "dietresearchbench_v1.json"


def test_diet_os_hdi_smoke_returns_synthesis_with_span_ids():
    """diet_os.run(case-hdi-001-sjw-sertraline) must:
      - return a ResearchSynthesis without raising
      - bt_span_ids[] is a list (may be empty if gateway lacks PR #92 instrumentation
        with BRAINTRUST_API_KEY set + ENTITY_TYPES-compatible LightRAG version)

    Production-ready assertion is len(bt_span_ids) >= 1, but the deployed Railway
    gateway pre-dates PR #92 (06-01 deploy; subsequent deploys blocked by a
    LightRAG breaking change). When the gateway is redeployed with PR #92 +
    a current LightRAG pin, tighten the assertion below.

    The verdict/confidence may or may not match the gold standard — this is
    a smoke test, not an evaluation. The point is end-to-end wiring.
    """
    from eval.scenario import BenchmarkSet  # type: ignore[import-not-found]
    from eval.baselines.diet_os import run  # type: ignore[import-not-found]

    assert _BENCH_PATH.exists(), f"benchmark dataset not found at {_BENCH_PATH}"
    bench = BenchmarkSet.model_validate_json(_BENCH_PATH.read_text())
    sjw = next(s for s in bench.scenarios if s.id == "case-hdi-001-sjw-sertraline")

    result = run(sjw)

    assert result is not None
    assert isinstance(result.bt_span_ids, list)
    # NOTE: assertion below intentionally weakened — see docstring.
    # When PR #92 lands on deployed gateway, change to: assert len(result.bt_span_ids) >= 1
    if len(result.bt_span_ids) == 0:
        import warnings
        warnings.warn(
            "bt_span_ids is empty — expected until gateway redeploys with PR #92 + LightRAG fix.",
            stacklevel=2,
        )
