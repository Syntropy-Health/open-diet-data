"""Shared LightRAG initialization helper.

Centralizes the embedding/storage configuration that previously lived
inline in ingest_unified.py so HDI / snapshot / new ingest scripts can
reuse the same workspace + embedding model without drift.

Reads the following env vars (typically loaded from
``shrine-diet-bioactivity/lightrag/config_local.env`` or
``config_production.env`` plus the shared ``.env`` for Aura creds):

  EMBEDDING_BINDING        (ollama | openai)
  EMBEDDING_MODEL
  EMBEDDING_DIM
  EMBEDDING_BINDING_HOST
  LIGHTRAG_GRAPH_STORAGE   (Neo4JStorage)
  LIGHTRAG_KV_STORAGE
  LIGHTRAG_VECTOR_STORAGE
  LIGHTRAG_DOC_STATUS_STORAGE
  WORKING_DIR
  WORKSPACE
"""
from __future__ import annotations

import os
from functools import partial
from pathlib import Path
from typing import Tuple


# Module-load-time registration in upstream LightRAG STORAGE_IMPLEMENTATIONS — see Issue #13.
# Importing scoped_neo4j_*_storage modules triggers their module-level
# registration of ScopedNeo4JStorage / ScopedNeo4JVectorStorage into upstream
# LightRAG's STORAGE_IMPLEMENTATIONS whitelist.  This must happen before any
# LightRAG() call that passes either class name as graph_storage /
# vector_storage.  The tuple binding marks the imports as accessed for static
# analysis while preserving the side-effect-only intent.
try:
    import scoped_neo4j_storage as _sns  # pyright: ignore[reportMissingImports]
    import scoped_neo4j_vector_storage as _snvs  # pyright: ignore[reportMissingImports]
    _REGISTERED_SCOPED_STORAGES: tuple = (_sns, _snvs)
except ImportError:
    _REGISTERED_SCOPED_STORAGES = ()


# LM Studio (and some other local OpenAI-compatible servers) reject
# response_format={"type": "json_object"} with a 400 ("'response_format.type'
# must be 'json_schema' or 'text'").  Upstream lightrag-hku 1.5.0 hardcodes
# json_object for keyword extraction (operate.py:4099), so the translation
# has to happen at our llm_model_func boundary.  This free-form object schema
# is the LM-Studio-accepted equivalent of json_object.
_JSON_SCHEMA_FREEFORM = {
    "type": "json_schema",
    "json_schema": {"name": "freeform_json", "schema": {"type": "object"}},
}


def _resolved_llm_base_url() -> str:
    """Base URL the openai-binding LLM client will actually use."""
    return os.getenv("OPENAI_API_BASE") or os.getenv("LLM_BINDING_HOST") or ""


def make_llm_func():
    """Return an async ``llm_model_func`` for the openai binding.

    Wraps ``openai_complete_if_cache`` (model from env ``LLM_MODEL``, falling
    back to ``gpt-4o-mini`` for parity with ``gpt_4o_mini_complete``) and,
    before calling through, rewrites ``response_format={"type":"json_object"}``
    to the LM-Studio-compatible free-form ``json_schema`` shape when the
    resolved base URL points at localhost/127.0.0.1 or when env
    ``LLM_JSON_SCHEMA_COMPAT=1`` forces it.  The ollama binding path is not
    affected (this helper is only used for openai bindings).
    """
    from lightrag.llm.openai import openai_complete_if_cache

    model = os.getenv("LLM_MODEL") or "gpt-4o-mini"

    async def llm_func(prompt, system_prompt=None, history_messages=None, **kwargs):
        rf = kwargs.get("response_format")
        if isinstance(rf, dict) and rf.get("type") == "json_object":
            base_url = _resolved_llm_base_url()
            is_local = "localhost" in base_url or "127.0.0.1" in base_url
            if is_local or os.getenv("LLM_JSON_SCHEMA_COMPAT") == "1":
                kwargs = {**kwargs, "response_format": _JSON_SCHEMA_FREEFORM}
        return await openai_complete_if_cache(
            model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            **kwargs,
        )

    return llm_func


def assert_workspace_embedding(model, dim, neo4j_uri, user, password, workspace):
    """Guard a Neo4j-backed workspace against embedding-space mixing.

    Reads a ``WorkspaceMeta`` node labelled with the workspace.  If absent,
    binds the workspace to the given embedding model + dim.  If present and
    mismatched, raises ``SystemExit`` — refusing to mix embedding spaces.
    """
    from neo4j import GraphDatabase

    dim = int(dim)
    driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))
    try:
        with driver.session() as session:
            rec = session.run(
                f"MATCH (m:`{workspace}`:WorkspaceMeta) "
                "RETURN m.embedding_model AS model, m.embedding_dim AS dim"
            ).single()
            if rec is None:
                session.run(
                    f"CREATE (m:`{workspace}`:WorkspaceMeta "
                    "{embedding_model: $model, embedding_dim: $dim})",
                    model=model,
                    dim=dim,
                )
                print(
                    f"[workspace-guard] bound workspace '{workspace}' "
                    f"to {model}/{dim}"
                )
                return
            if rec["model"] != model or int(rec["dim"]) != dim:
                raise SystemExit(
                    f"[workspace-guard] workspace '{workspace}' is bound to "
                    f"embedding {rec['model']}/{rec['dim']} but env requests "
                    f"{model}/{dim} — refusing to mix embedding spaces. "
                    "Change WORKSPACE or EMBEDDING_MODEL/EMBEDDING_DIM."
                )
            print(f"[workspace-guard] workspace '{workspace}' OK: {model}/{dim}")
    finally:
        driver.close()


def init_lightrag(working_dir: str | None = None):
    """Construct and initialize a LightRAG instance from current env.

    Returns a tuple ``(rag, workspace)``. Caller must ``await
    rag.initialize_storages()`` then ``await rag.finalize_storages()``
    when done.
    """
    from lightrag import LightRAG
    from lightrag.utils import EmbeddingFunc

    embedding_binding = os.getenv("EMBEDDING_BINDING", "ollama")
    embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
    embedding_dim = int(os.getenv("EMBEDDING_DIM", "768"))
    embedding_host = os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434")

    if embedding_binding == "ollama":
        from lightrag.llm.ollama import ollama_embed, ollama_model_complete

        llm_func = ollama_model_complete
        embed_func = EmbeddingFunc(
            embedding_dim=embedding_dim,
            max_token_size=8192,
            func=partial(
                ollama_embed.func,
                embed_model=embedding_model,
                host=embedding_host,
            ),
        )
    else:
        from lightrag.llm.openai import openai_embed

        llm_func = make_llm_func()
        embed_func = EmbeddingFunc(
            embedding_dim=embedding_dim,
            max_token_size=8192,
            func=partial(openai_embed.func, model=embedding_model),
        )

    wd = working_dir or os.getenv("WORKING_DIR", "./rag_storage_local")
    Path(wd).mkdir(parents=True, exist_ok=True)

    graph_storage = os.getenv("LIGHTRAG_GRAPH_STORAGE", "NetworkXStorage")
    kv_storage = os.getenv("LIGHTRAG_KV_STORAGE", "JsonKVStorage")
    vector_storage = os.getenv("LIGHTRAG_VECTOR_STORAGE", "NanoVectorDBStorage")
    doc_status_storage = os.getenv(
        "LIGHTRAG_DOC_STATUS_STORAGE", "JsonDocStatusStorage"
    )
    workspace = os.getenv("WORKSPACE", "unified_diet_kg")

    rag = LightRAG(
        working_dir=wd,
        llm_model_func=llm_func,
        embedding_func=embed_func,
        graph_storage=graph_storage,
        kv_storage=kv_storage,
        vector_storage=vector_storage,
        doc_status_storage=doc_status_storage,
        workspace=workspace,
    )
    return rag, workspace
