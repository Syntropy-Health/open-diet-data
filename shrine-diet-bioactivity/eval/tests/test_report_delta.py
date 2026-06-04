"""Tests for render_delta_table() and --baseline-results-dir CLI behaviour."""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]


def test_render_delta_table_emits_per_system_per_metric_rows(tmp_path: Path):
    _ = tmp_path  # accept fixture even though we don't use it
    baseline = {
        "diet_os": {"verdict_kappa": 0.258, "hdi_recall": 0.713, "defer_acc": 0.699},
        "single_llm": {"verdict_kappa": 0.056, "hdi_recall": 0.000, "defer_acc": 0.550},
    }
    new = {
        "diet_os": {"verdict_kappa": 0.331, "hdi_recall": 0.821, "defer_acc": 0.750},
        "single_llm": {"verdict_kappa": 0.060, "hdi_recall": 0.000, "defer_acc": 0.550},
    }
    from eval.report import render_delta_table  # type: ignore[import-not-found]
    out = render_delta_table(baseline=baseline, new=new, metrics=["verdict_kappa", "hdi_recall", "defer_acc"])
    assert "diet_os" in out
    assert "+0.073" in out  # 0.331 - 0.258
    assert "+0.108" in out  # 0.821 - 0.713
    # baseline-stable rows should still show, with 0.000 delta
    assert "single_llm" in out


def test_render_delta_table_marks_material_changes_above_threshold(tmp_path: Path):
    _ = tmp_path
    baseline = {"diet_os": {"verdict_kappa": 0.258}}
    new = {"diet_os": {"verdict_kappa": 0.331}}
    from eval.report import render_delta_table  # type: ignore[import-not-found]
    out = render_delta_table(baseline=baseline, new=new, metrics=["verdict_kappa"], material_threshold=0.05)
    assert "**" in out  # material change formatted bold
