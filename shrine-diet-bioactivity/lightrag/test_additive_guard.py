"""Both-arm tests for the additive-only ingest guard (#233b).

Pure-logic arms always run. The live-Neo4j arms (scratch workspace) run only when
NEO4J_URI is reachable — they prove the snapshot query against a real graph and
that a real DELETE trips the guard.
"""
from __future__ import annotations

import os

import pytest

from additive_guard import assert_additive, diff_additive, snapshot_workspace_counts

pytestmark = pytest.mark.unit


# ---- pure-logic arms (no I/O) ----

def test_additive_passes_when_counts_grow_or_hold():
    before = {"labels": {"Compound": 100, "Target": 10}, "rels": {"TARGETS_PROTEIN": 50}}
    after = {"labels": {"Compound": 100, "Target": 12, "VectorChunk": 5}, "rels": {"TARGETS_PROTEIN": 60}}
    assert diff_additive(before, after) == []
    assert_additive(before, after)  # must not raise


def test_replacing_shrink_is_a_violation():
    before = {"labels": {"Compound": 100}, "rels": {"TARGETS_PROTEIN": 50}}
    after = {"labels": {"Compound": 40}, "rels": {"TARGETS_PROTEIN": 50}}
    v = diff_additive(before, after)
    assert len(v) == 1 and "Compound" in v[0] and "100 -> 40" in v[0]
    with pytest.raises(SystemExit):
        assert_additive(before, after)


def test_dropped_rel_type_is_a_violation():
    # A rel type vanishing entirely (after count 0) is the chain-tool-killer case.
    before = {"labels": {"Compound": 1}, "rels": {"TARGETS_PROTEIN": 6465}}
    after = {"labels": {"Compound": 1}, "rels": {}}
    v = diff_additive(before, after)
    assert len(v) == 1 and "TARGETS_PROTEIN" in v[0] and "6465 -> 0" in v[0]


def test_new_labels_and_types_are_not_violations():
    before = {"labels": {"Compound": 1}, "rels": {}}
    after = {"labels": {"Compound": 1, "VectorChunk": 99}, "rels": {"DIRECTED": 10}}
    assert diff_additive(before, after) == []


# ---- live-Neo4j arms (scratch workspace) ----

def _driver_or_skip():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        pytest.skip("neo4j driver not installed")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    pw = os.getenv("NEO4J_PASSWORD", "localdevpass")
    try:
        d = GraphDatabase.driver(uri, auth=(user, pw))
        with d.session() as s:
            s.run("RETURN 1").single()
        return d
    except Exception:
        pytest.skip(f"Neo4j not reachable at {uri}")


@pytest.mark.integration
def test_live_snapshot_and_red_arm():
    d = _driver_or_skip()
    ws = "additive_guard_test_ws"
    try:
        with d.session() as s:
            s.run(f"MATCH (n:`{ws}`) DETACH DELETE n")
            # seed: 3 Compound, 2 Target, 2 typed edges
            s.run(
                f"CREATE (c1:`{ws}`:Compound),(c2:`{ws}`:Compound),(c3:`{ws}`:Compound),"
                f"(t1:`{ws}`:Target),(t2:`{ws}`:Target),"
                f"(c1)-[:TARGETS_PROTEIN]->(t1),(c2)-[:TARGETS_PROTEIN]->(t2)"
            )
            before = snapshot_workspace_counts(s, ws)
            assert before["labels"]["Compound"] == 3
            assert before["rels"]["TARGETS_PROTEIN"] == 2

            # GREEN arm: add a Compound + a VectorChunk (new label)
            s.run(f"CREATE (c:`{ws}`:Compound),(:`{ws}`:VectorChunk)")
            after_add = snapshot_workspace_counts(s, ws)
            assert_additive(before, after_add)  # additive -> must not raise
            assert after_add["labels"]["Compound"] == 4

            # RED arm: delete a Target (a replacing operation)
            s.run(f"MATCH (t:`{ws}`:Target) WITH t LIMIT 1 DETACH DELETE t")
            after_del = snapshot_workspace_counts(s, ws)
            with pytest.raises(SystemExit) as ei:
                assert_additive(before, after_del)
            assert "Target" in str(ei.value)
        finally_ok = True
    finally:
        with d.session() as s:
            s.run(f"MATCH (n:`{ws}`) DETACH DELETE n")
        d.close()
    assert finally_ok
