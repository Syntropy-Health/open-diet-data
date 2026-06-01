# HANDOFF — Milvus backfill from Aura (2026-06-01)

Operational summary of the Milvus → kg-mcp federation backfill, run end-to-end
against the live Zilliz Cloud free-tier cluster (`in03-bfa386d3d80b8ce`) and
Aura instance `b7dbceab`.

## Why

The clinical-anchor embed pass (`scripts/embed_clinical_entities.py`) seeded
the `entities_vdb` Milvus collection with a curated 26,191-entity subset of
the 155,023-node KG. Relationships were completely un-embedded. Result:
`kg_query` semantic search worked on a fraction of the graph, and Layer-A
recall on Aura-side compounds was 17% at best.

This backfill closes that gap under the Zilliz free-tier 5 GB cap.

## Final state

### Collections (post-backfill)

| Collection | Rows | Coverage vs Aura |
|---|---:|---|
| `unified_diet_kg_entities` | **166,677** | Aura has 155,023; Milvus is at 108% (slight over from earlier-pass entity_id variants — see "Known caveats") |
| `unified_diet_kg_relationships` | **181,985** | **100%** (`TARGETS_PROTEIN`, `TREATS_SYMPTOM`, `ASSOCIATED_WITH_DISEASE`, `CONTAINS_COMPOUND`, `FOUND_IN_FOOD` all fully embedded) |
| `unified_diet_kg_chunks` | 131 | Synthetic anchor scaffolding from the original clinical-anchor pass; LightRAG requires non-empty chunks_vdb. |

### Storage envelope

- Estimated total usage: ~3.7 GB of 5 GB cap (≈75%).
- HNSW index overhead observed at ~1.4x raw (lower than the conservative
  2x assumption used at planning time).
- Remaining headroom: ~1.3 GB → room for ~80K more 2048-dim vectors if a
  future content-chunk backfill is wired in.

### Tier-by-tier breakdown

| Tier | Source | Count | Notes |
|---|---|---:|---|
| 0 | Clinical-anchor pass (pre-existing) | 26,191 | Embedded by `embed_clinical_entities.py`. |
| 1 | All Herb, Disease, Symptom, Target, Food | 50,648 | Embedded by `backfill_milvus_from_aura.py`. |
| 2 | Top-30K Compounds by relationship degree | 14,510 | All Compounds with ≥ 1 edge — the long tail at degree 0 was Tier 3. |
| 3 | Orphan Compounds (degree = 0) | 89,868 | Embedded after `--include-orphans` landed (PR #90). |

## Live `kg_query` validation — 8/8 useful

Verified against the live gateway `https://kg-mcp-test.up.railway.app/mcp`
using `mode="hybrid"` and `top_k=10`. Every probe returned a substantial,
KG-grounded answer (≥ 200 chars, no "do not have enough information"):

| Probe (label, query) | Answer length |
|---|---:|
| Compound — *What compounds does Curcuma longa contain?* | 854 chars |
| Compound — *What targets does CURCUMIN bind?* | 327 chars |
| Herb — *Tell me about Astragalus membranaceus and immune support* | 1,281 chars |
| Disease — *Treatments for type 2 diabetes* | 1,095 chars |
| Symptom — *What herbs treat fatigue?* | 1,038 chars |
| Target — *What is NF-kappa-B p65?* | 668 chars |
| Food — *Compounds in olive oil* | 1,752 chars |
| Concept — *Which compounds have anti-cancer activity?* | 297 chars |

## Caller-side recommendation — use `mode="hybrid"`, `top_k=10`

Local-mode pure-entity search (`mode="local"`, `top_k=5`) regresses on
broad-concept queries after the orphan-compound backfill, because the 89K
zero-degree compounds dilute the top-5 vector hits. Switching to
`mode="hybrid"` uses both entity and relationship vectors (the latter
now 100% indexed), which fully recovers grounding. `top_k=10` further
broadens the candidate pool so relevant entities are not pushed below
the cutoff.

The Syntropy-Journals chat-agent integration (PR
[#911](https://github.com/Syntropy-Health/SyntropyJournal/pull/911))
already calls `kg_query` with `mode="hybrid"` and exercises this
configuration in `tests/integration/test_kg_mcp_live_contract.py`.

## Operational runbook — re-running the backfill

The backfill is idempotent. Re-running on a converged index is a no-op
(the script reads the full Milvus id-set and skips anything already
embedded). To re-run from scratch (e.g. after a schema change):

```bash
cd shrine-diet-bioactivity

# Tier-1 + Tier-2 + orphans, all-in-one
infisical run --env=prod --path=/mcp/kg/ -- \
infisical run --env=prod --path=/research/shrine-diet-bioactivity/ -- \
    python scripts/backfill_milvus_from_aura.py \
        --entities-only --include-orphans \
        --batch-size 128

# Then relationships
infisical run --env=prod --path=/mcp/kg/ -- \
infisical run --env=prod --path=/research/shrine-diet-bioactivity/ -- \
    python scripts/backfill_milvus_from_aura.py \
        --relationships-only \
        --batch-size 128
```

Observed throughput: ~10 entities/s, ~30 relationships/s. Free-tier
OpenRouter rate limits cap embedding throughput; Aura per-batch
neighborhood JOIN dominates entity-pass latency.

### Recovery from interrupts

The script catches transient Aura failures (`ServiceUnavailable`,
`DatabaseUnavailable`, DNS resolution flakes) with exponential
backoff (see `_aura_retry`, PRs #88 and #89). On a hard kill, just
re-run the same command — the Milvus skip-list picks up where you
left off.

## Known caveats

1. **Entity count > Aura node count** (166,677 vs 155,023). Cause:
   the original clinical-anchor pass produced some entity_id variants
   (case / whitespace normalisation differences) that don't match the
   current Aura entity_id format. These extra rows are harmless but
   inflate the count. A future cleanup PR could de-duplicate by
   normalising the primary key.

2. **`chunks_vdb` is scaffolding.** Of the 131 chunks, none represent
   real source documents — they are synthetic anchors emitted by the
   clinical-anchor script so LightRAG's chunk-side query path doesn't
   error. Consequence: `kg_query` `references` field stays empty; the
   answer body is grounded but provenance hyperlinks aren't surfaced.
   A real citation-style chunk backfill (one chunk per entity with
   `source_id` provenance) is the natural follow-up — fits within the
   ~1.3 GB Milvus headroom.

3. **Free-tier rate limits.** OpenRouter free model
   (`nvidia/llama-nemotron-embed-vl-1b-v2:free`) caps the backfill
   at ~10–30 emb/s. Upgrading the embedder is the only meaningful
   way to bring full-backfill walltime under 30 min.

## Cross-links

- Backfill script: `shrine-diet-bioactivity/scripts/backfill_milvus_from_aura.py`
- Clinical-anchor pass (prior generation): `shrine-diet-bioactivity/scripts/embed_clinical_entities.py`
- Milvus DI in scoped_server: `shrine-diet-bioactivity/lightrag/scoped_server.py` (`_apply_zilliz_env_shim`, `_resolve_vector_storage`)
- Consumer-side integration: `Syntropy-Health/SyntropyJournal#911`
