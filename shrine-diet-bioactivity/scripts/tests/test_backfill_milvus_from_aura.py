"""Smoke + composer tests for backfill_milvus_from_aura.py.

The full backfill is a long-running network operation that we don't
exercise in unit tests. These cover the pure-logic surface:

* CLI parses ``--help`` cleanly.
* ``compose_entity_text`` mirrors the format from the clinical-anchor
  pass so query-vector geometry stays consistent.
* ``compose_relationship_text`` produces the expected one-line paraphrase
  for each documented rel type.
* ``relationship_id`` is deterministic + collision-resistant.
* ``safe_milvus_id`` clamps oversized raw IDs.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parent.parent / "backfill_milvus_from_aura.py"
)


pytestmark = [pytest.mark.unit]


# ─── CLI smoke ────────────────────────────────────────────────────────────


def test_help_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    out = (proc.stdout + proc.stderr).lower()
    assert "backfill" in out
    assert "--entities-only" in out
    assert "--relationships-only" in out
    assert "--compound-degree-top" in out


# ─── Text composers ──────────────────────────────────────────────────────


def _import_backfill():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import backfill_milvus_from_aura as bf  # type: ignore
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return bf


def test_compose_entity_text_includes_id_label_description():
    bf = _import_backfill()
    text = bf.compose_entity_text(
        "Curcumin",
        "Compound",
        "Polyphenol from Curcuma longa.",
        edges=[],
    )
    assert "Curcumin" in text
    assert "Compound" in text
    assert "Polyphenol" in text


def test_compose_entity_text_groups_edges_by_rel_and_direction():
    bf = _import_backfill()
    text = bf.compose_entity_text(
        "Curcumin",
        "Compound",
        "",
        edges=[
            {"rel": "TARGETS_PROTEIN", "nbr": "NFKB1", "out": True},
            {"rel": "TARGETS_PROTEIN", "nbr": "COX2", "out": True},
            {"rel": "CONTAINS_COMPOUND", "nbr": "Curcuma longa", "out": False},
        ],
    )
    assert "TARGETS_PROTEIN" in text
    # Outbound uses →; inbound uses ←
    assert "→" in text
    assert "←" in text
    assert "NFKB1" in text
    assert "Curcuma longa" in text


def test_compose_entity_text_truncates_at_max_chars():
    bf = _import_backfill()
    big_edges = [
        {"rel": "TARGETS_PROTEIN", "nbr": f"T{i}", "out": True}
        for i in range(1000)
    ]
    text = bf.compose_entity_text("X", "Compound", "", edges=big_edges)
    assert len(text) <= bf.MAX_TEXT_CHARS


def test_compose_relationship_text_has_all_three_parts():
    bf = _import_backfill()
    text = bf.compose_relationship_text(
        "Astragalus membranaceus",
        "TREATS_SYMPTOM",
        "Aging",
        "Herb",
        "Symptom",
    )
    assert "Astragalus membranaceus" in text
    assert "TREATS_SYMPTOM" in text
    assert "Aging" in text
    assert "(Herb)" in text and "(Symptom)" in text


def test_compose_relationship_text_handles_missing_labels():
    bf = _import_backfill()
    text = bf.compose_relationship_text(
        "Curcumin", "TARGETS_PROTEIN", "NFKB1", None, None
    )
    # Still well-formed even without labels.
    assert "Curcumin" in text
    assert "TARGETS_PROTEIN" in text
    assert "NFKB1" in text


# ─── Relationship id determinism ─────────────────────────────────────────


def test_relationship_id_is_deterministic():
    bf = _import_backfill()
    a = bf.relationship_id("Curcumin", "TARGETS_PROTEIN", "NFKB1")
    b = bf.relationship_id("Curcumin", "TARGETS_PROTEIN", "NFKB1")
    assert a == b
    assert a.startswith("rel-")


def test_relationship_id_distinguishes_direction():
    bf = _import_backfill()
    fwd = bf.relationship_id("Curcumin", "TARGETS_PROTEIN", "NFKB1")
    rev = bf.relationship_id("NFKB1", "TARGETS_PROTEIN", "Curcumin")
    assert fwd != rev


# ─── safe_milvus_id ──────────────────────────────────────────────────────


def test_safe_milvus_id_passes_simple_names():
    bf = _import_backfill()
    assert bf.safe_milvus_id("ACACETIN", "ent") == "ACACETIN"


def test_safe_milvus_id_hashes_special_chars():
    """IDs containing characters outside [A-Za-z0-9_-:] get md5-hashed so
    the Milvus VARCHAR(64) primary key stays compliant."""
    bf = _import_backfill()
    out = bf.safe_milvus_id("(+)-(6R)-foo bar/baz", "ent")
    assert out.startswith("ent-")
    assert len(out) == len("ent-") + 32


def test_safe_milvus_id_hashes_oversize():
    bf = _import_backfill()
    out = bf.safe_milvus_id("A" * 200, "ent")
    assert len(out) <= 64
