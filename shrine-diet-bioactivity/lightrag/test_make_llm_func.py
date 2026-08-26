"""Unit tests for make_llm_func's response_format rewrite — no live LLM.

Covers both arms of the json_object -> json_schema shim (T2): it fires only for
a local/forced endpoint and only for type=="json_object", and it targets the
same base_url it inspects (the reconciliation of the base_url/endpoint finding).

Hermetic: a fake ``lightrag.llm.openai`` is injected into ``sys.modules`` so the
test does not depend on whether the local ``lightrag/`` dir or the installed
``lightrag-hku`` package wins the import (they otherwise shadow each other when
pytest runs from this directory).
"""
import asyncio
import sys
import types

import pytest

import lightrag_init

pytestmark = pytest.mark.unit


@pytest.fixture
def captured(monkeypatch):
    """Inject a fake lightrag.llm.openai.openai_complete_if_cache spy."""
    calls = {}

    async def fake_complete(model, prompt, system_prompt=None, history_messages=None, **kwargs):
        calls["model"] = model
        calls["base_url"] = kwargs.get("base_url")
        calls["api_key"] = kwargs.get("api_key")
        calls["response_format"] = kwargs.get("response_format")
        return "ok"

    pkg = types.ModuleType("lightrag")
    llm = types.ModuleType("lightrag.llm")
    openai_mod = types.ModuleType("lightrag.llm.openai")
    openai_mod.openai_complete_if_cache = fake_complete
    monkeypatch.setitem(sys.modules, "lightrag", pkg)
    monkeypatch.setitem(sys.modules, "lightrag.llm", llm)
    monkeypatch.setitem(sys.modules, "lightrag.llm.openai", openai_mod)
    return calls


def _run(func, **kw):
    return asyncio.run(func("p", **kw))


def test_rewrites_json_object_when_local(monkeypatch, captured):
    monkeypatch.setenv("LLM_BINDING_HOST", "http://localhost:1234/v1")
    monkeypatch.setenv("LLM_MODEL", "google/gemma-4-12b-qat")
    monkeypatch.delenv("LLM_JSON_SCHEMA_COMPAT", raising=False)
    f = lightrag_init.make_llm_func()
    _run(f, response_format={"type": "json_object"})
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["base_url"] == "http://localhost:1234/v1"  # detection == destination


def test_passthrough_json_schema_and_text(monkeypatch, captured):
    monkeypatch.setenv("LLM_BINDING_HOST", "http://localhost:1234/v1")
    f = lightrag_init.make_llm_func()
    schema = {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}}
    _run(f, response_format=schema)
    assert captured["response_format"] is schema  # untouched
    _run(f, response_format={"type": "text"})
    assert captured["response_format"] == {"type": "text"}


def test_no_rewrite_for_remote_json_object(monkeypatch, captured):
    monkeypatch.setenv("LLM_BINDING_HOST", "https://openrouter.ai/api/v1")
    monkeypatch.delenv("LLM_JSON_SCHEMA_COMPAT", raising=False)
    f = lightrag_init.make_llm_func()
    _run(f, response_format={"type": "json_object"})
    assert captured["response_format"] == {"type": "json_object"}  # left as-is for a real API


def test_force_compat_flag_rewrites_remote(monkeypatch, captured):
    monkeypatch.setenv("LLM_BINDING_HOST", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_JSON_SCHEMA_COMPAT", "1")
    f = lightrag_init.make_llm_func()
    _run(f, response_format={"type": "json_object"})
    assert captured["response_format"]["type"] == "json_schema"


def test_empty_base_url_is_not_local(monkeypatch, captured):
    monkeypatch.delenv("LLM_BINDING_HOST", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("LLM_JSON_SCHEMA_COMPAT", raising=False)
    f = lightrag_init.make_llm_func()  # must not raise on empty base url
    _run(f, response_format={"type": "json_object"})
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["base_url"] is None
