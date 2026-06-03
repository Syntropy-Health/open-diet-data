"""Live integration tests for MilvusVectorStore against Zilliz/Milvus.

Gated by ``ZILLIZ_URI`` (or ``MILVUS_URI``) in the environment. When the
secret is absent — PRs from forks, fresh dev clones — every test in this
module skips cleanly with a clear reason. Trusted CI runs that have the
secret mirrored from Infisical will execute these.

These are *not* unit tests — they hit a real cluster. The collection used
is a per-run sentinel (``test_kg_entities_<uuid>``) so we never collide
with the prod ``kg_entities`` collection. The tests drop the sentinel
collection on teardown so a failed run doesn't leak storage.
"""
from __future__ import annotations

import os
import uuid

import pytest

from kg_mcp.storage import VectorEntry
from kg_mcp.storage.milvus import MilvusConfig, MilvusVectorStore

# Braintrust tracing — silent no-op without BRAINTRUST_API_KEY env. Wrap
# each test so live cluster round-trips show up in the dashboard with
# input + result-shape metadata for retroactive debugging.
try:
    from ..e2e._braintrust_logger import bt_span  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — defensive
    from contextlib import contextmanager

    @contextmanager
    def bt_span(name: str, **inputs):  # type: ignore[no-redef]
        class _Stub:
            def log(self, **kwargs):
                pass

        yield _Stub()


pytestmark = [pytest.mark.integration]


def _milvus_env() -> dict[str, str]:
    """Snapshot the Milvus env vars or skip if URI is missing."""
    env = {
        k: os.environ[k]
        for k in (
            "MILVUS_URI",
            "MILVUS_TOKEN",
            "MILVUS_USER",
            "MILVUS_PASSWORD",
            "ZILLIZ_URI",
            "ZILLIZ_TOKEN",
            "ZILLIZ_DB_USER",
            "ZILLIZ_DB_PASSWORD",
            "EMBEDDING_DIM",
        )
        if k in os.environ
    }
    if not (env.get("MILVUS_URI") or env.get("ZILLIZ_URI")):
        pytest.skip(
            "MILVUS_URI / ZILLIZ_URI not set; live Milvus tests skipped."
        )
    # Normalise to the names MilvusConfig.from_env expects.
    if "MILVUS_URI" in env and "ZILLIZ_URI" not in env:
        env["ZILLIZ_URI"] = env["MILVUS_URI"]
    if "MILVUS_TOKEN" in env and "ZILLIZ_TOKEN" not in env:
        env["ZILLIZ_TOKEN"] = env["MILVUS_TOKEN"]
    return env


@pytest.fixture
def milvus_store():
    """Yield a MilvusVectorStore bound to a per-test sentinel collection."""
    env = _milvus_env()
    collection = f"test_kg_entities_{uuid.uuid4().hex[:8]}"
    env["ZILLIZ_COLLECTION"] = collection
    env.setdefault("EMBEDDING_DIM", "4")  # tiny dim for fast schema bootstrap

    cfg = MilvusConfig.from_env(env)
    store = MilvusVectorStore(cfg)
    try:
        yield store
    finally:
        # Best-effort cleanup; a leaked sentinel is loud-but-harmless.
        try:
            store.drop()
        except Exception as exc:  # noqa: BLE001 — defensive teardown
            import warnings

            warnings.warn(f"Milvus sentinel cleanup failed: {exc}")


def test_health_via_count_zero_on_fresh_collection(milvus_store):
    """Smoke probe: the live cluster responds + a fresh collection is empty."""
    with bt_span(
        "test_health_via_count_zero_on_fresh_collection",
        backend="milvus",
        collection=milvus_store._config.collection,
    ) as span:
        count = milvus_store.count()
        span.log(output={"count": count})
        assert count == 0


def test_upsert_then_query_returns_entry(milvus_store):
    """Round-trip a tiny vector through the live cluster."""
    with bt_span(
        "test_upsert_then_query_returns_entry",
        backend="milvus",
        collection=milvus_store._config.collection,
        upsert_count=1,
        top_k=1,
    ) as span:
        milvus_store.upsert(
            [
                VectorEntry(
                    entity_id="ent-roundtrip",
                    vector=[1.0, 0.0, 0.0, 0.0],
                    entity_name="RoundTrip",
                    content="probe entity for live Milvus",
                    source_id="integration:probe",
                    file_path="test",
                    scope="shared",
                ),
            ]
        )
        # Milvus's flush-on-search is eventual; the search call below
        # waits for consistent read by default.
        hits = milvus_store.query([1.0, 0.0, 0.0, 0.0], top_k=1)
        span.log(
            output={
                "hit_count": len(hits),
                "top_entity_id": hits[0].entry.entity_id if hits else None,
                "top_score": hits[0].score if hits else None,
            }
        )
        assert len(hits) == 1
        assert hits[0].entry.entity_id == "ent-roundtrip"
        assert hits[0].entry.source_id == "integration:probe"


def test_scope_filter_excludes_other_scopes(milvus_store):
    """The metadata-filter path actually filters at the cluster level."""
    with bt_span(
        "test_scope_filter_excludes_other_scopes",
        backend="milvus",
        collection=milvus_store._config.collection,
        upsert_count=2,
        scope_filter="shared",
        top_k=5,
    ) as span:
        milvus_store.upsert(
            [
                VectorEntry(
                    entity_id="ent-shared",
                    vector=[0.0, 1.0, 0.0, 0.0],
                    entity_name="Shared",
                    scope="shared",
                ),
                VectorEntry(
                    entity_id="ent-private",
                    vector=[0.0, 1.0, 0.0, 0.0],
                    entity_name="Private",
                    scope="tenant-foo",
                ),
            ]
        )
        shared_hits = milvus_store.query([0.0, 1.0, 0.0, 0.0], top_k=5, scope="shared")
        shared_ids = {h.entry.entity_id for h in shared_hits}
        span.log(
            output={
                "shared_hit_count": len(shared_hits),
                "shared_ids": sorted(shared_ids),
            }
        )
        assert "ent-shared" in shared_ids
        assert "ent-private" not in shared_ids
