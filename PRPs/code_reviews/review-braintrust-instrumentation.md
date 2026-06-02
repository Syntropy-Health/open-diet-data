# Code Review: Braintrust Observability Instrumentation

**PRs reviewed**: shrine-diet-bioactivity#92 (`feat/braintrust-runtime-tracing`) and SyntropyJournal#920 (`feat/braintrust-test-tracing`)
**Date**: 2026-06-02
**Reviewer**: Claude Sonnet 4.6 (independent second opinion)

---

## Scope

- **Reviewing**: `git diff main...feat/braintrust-runtime-tracing` (PR1) + `git diff test...feat/braintrust-test-tracing` (PR2)
- **PR1 files**: `mcp/src/kg_mcp/braintrust_runtime.py`, `mcp/src/kg_mcp/tools.py`, `mcp/tests/e2e/_braintrust_logger.py`, `mcp/tests/e2e/test_agentic_kg_query.py`, `mcp/tests/integration/test_milvus_vectorstore.py`, `shrine-diet-bioactivity/eval/tests/_braintrust_logger.py`, `.github/workflows/deploy-mcp.yml`, `.github/workflows/mcp-ci.yml`
- **PR2 files**: `tests/_braintrust_test_logger.py`, `tests/e2e/test_agentic_kg_grounding.py`, `tests/integration/test_kg_mcp_live_contract.py`, `tests/unit/test_*.py` (3 files), `.github/workflows/deploy-test-async.yml`, `syntropy_journals/app/functions/infisical/client.py`, `syntropy_journals/app/functions/llm/middleware/observability.py`, `syntropy_journals/app/functions/llm/router/chat_router.py`, `syntropy_journals/app/version.py`
- **Guidelines**: project CLAUDE.md + `~/.claude/rules/`

---

## Critical Issues (90–100)

### Issue 1: `test_kg_herb_to_symptoms_returns_provenance_tagged_chain` — assertions leak outside the span context manager

**Confidence**: 95/100
**Location**: `Syntropy-Journals/tests/integration/test_kg_mcp_live_contract.py:257–262`
**Category**: Bug — span coverage gap, silent span-end race

**Problem**:
The `with bt_span(...)` block ends at line 256. Two of the three assertions fall outside it:

```python
        assert not envelope.get("isError"), f"tool returned error: {envelope}"
    assert len(chains) >= 1, ...     # ← OUTSIDE the with-block

    for chain in chains:
        for edge in chain.get("edges", []):
            sid = edge.get("source_id", "")
            assert _SOURCE_PREFIX.match(sid), ...  # ← also OUTSIDE
```

This is an indentation bug. The `assert len(chains) >= 1` line and the full provenance-prefix loop are dedented one level past the `with bt_span(...)` scope. Consequences:

1. **Span coverage is incomplete**: when the chain-count or prefix assertion fails, `span.end()` has already been called (by the context-manager's `finally`). The span exists in Braintrust with `is_error=False` and the correct `chain_count`, but the failure that caused the CI break is unrecorded. The feature's stated goal — "a failed agent call can be retroactively debugged with the trace" — is not met for this failure mode.

2. **`chains` is used after the `finally` block**: `span.end()` calls Braintrust's network flush. If the flush raises (unlikely but possible given the broad except on end), the variable `chains` is still valid and the assertions run correctly — so this is not a runtime break. However the semantics are surprising and the span telemetry will be misleading.

The analogous test in `test_agentic_kg_grounding.py` (lines 553–557) does NOT have this problem — the provenance assert is inside the span block. The contract probe test is the sole outlier.

**Suggested Fix**: Indent `assert len(chains) >= 1` and the `for chain in chains` loop into the `with bt_span(...)` body:

```python
        span.log(output={...})
        assert not envelope.get("isError"), f"tool returned error: {envelope}"
        assert len(chains) >= 1, f"expected ≥ 1 chain, got {chains}"

        for chain in chains:
            for edge in chain.get("edges", []):
                sid = edge.get("source_id", "")
                assert _SOURCE_PREFIX.match(sid), f"unknown source_id prefix: {sid!r}"
```

---

## Important Issues (80–89)

### Issue 2: `BRAINTRUST_API_KEY` passes through the shell unquoted via `$BRAINTRUST_API_KEY` expansion

**Confidence**: 85/100
**Location**: `shrine-diet-bioactivity/.github/workflows/deploy-mcp.yml:203–205`
**Category**: Security / Correctness

**Problem**:
The Railway variables step uses:

```yaml
--set "BRAINTRUST_API_KEY=$BRAINTRUST_API_KEY"
```

The shell expands `$BRAINTRUST_API_KEY` before the Railway CLI processes it. If the secret contains shell-special characters (`!`, `$`, backtick, newline), the expansion produces an argument that either word-splits incorrectly or triggers unexpected shell behaviour. Braintrust API keys (`bt-...`) are alphanumeric-plus-hyphen and don't contain special characters in practice, so this is low-probability for the current key format — but it's still bad form for a secret, and the pattern should be safe-by-construction.

The safer Railway CLI form uses `--set KEY=VALUE` via a heredoc or process-substitution approach, but the most pragmatic fix that Railway's CLI actually supports is to pass the value through `printf '%s'` into an env-file and use `--env-file`, or at minimum to use `$'...'` quoting. However, Railway's `--set` flag reads the full `KEY=VALUE` string as one argument, so the real fix is ensuring no further word-splitting occurs:

```yaml
run: |
  railway variables \
    --service "${{ env.RAILWAY_SERVICE }}" \
    --environment "$ENV_NAME" \
    --set "BRAINTRUST_API_KEY=${BRAINTRUST_API_KEY}" \
    --set "BRAINTRUST_PROJECT=shrine-diet-bioactivity"
```

`${VAR}` vs `$VAR` makes no practical difference here — the actual safe approach is to confirm Railway CLI accepts `--env-file` and pass secrets that way. For the current key format this is a low-severity concern, but the team should document why it's accepted or switch to the env-file approach when available.

**Note**: The `if: ${{ secrets.BRAINTRUST_API_KEY != '' }}` guard correctly prevents the step from running on fork PRs — that part is clean.

---

### Issue 3: Module-level `_INIT_ATTEMPTED` singleton breaks across-test-session isolation when `BRAINTRUST_API_KEY` changes between test runs in the same process

**Confidence**: 80/100
**Location**: All four helper files (both `_braintrust_logger.py` copies, `_braintrust_test_logger.py`, `braintrust_runtime.py`)
**Category**: Quality / Testing

**Problem**:
All four helpers use a module-level `_INIT_ATTEMPTED: bool = False` + `_BT_LOGGER: Any = None` pair. `_maybe_init()` sets `_INIT_ATTEMPTED = True` on first call and never resets it. This is correct for production (one process, stable env) but creates a subtle issue in pytest sessions that change `BRAINTRUST_API_KEY` via `monkeypatch` or `patch.dict`:

```python
# First test: BRAINTRUST_API_KEY unset → _INIT_ATTEMPTED = True, _BT_LOGGER = None
# Second test: sets BRAINTRUST_API_KEY via monkeypatch → _maybe_init() returns None (cached)
```

In the current test suite, no test does this — all env-keyed tests use `_env_or_skip` and skip cleanly when the key is absent. But the Milvus and contract-probe tests both import the helper at module level, meaning any future test that patches `BRAINTRUST_API_KEY` after those modules are imported will silently get no-op spans.

This is an inherent limitation of the singleton pattern with module-level state. It's documented nowhere in the helpers, and the fix (add a `_reset_for_testing()` function guarded by an `if os.environ.get("PYTEST_CURRENT_TEST")` check) is low-priority but worth noting before the test surface grows further.

**This issue is not blocking for merge** — the current suite has no tests that trigger it.

---

## Specific Questions — Direct Answers

### 1. Fail-soft correctness

The fail-soft analysis is clean. Tracing through every path in both `tool_span` and `bt_span`:

- `_maybe_init()` path: key absent → return None (no raise possible). SDK ImportError → return None. `braintrust.init_logger` exception → caught, return None. All paths terminate safely.
- `start_span` exception → caught by the outer try/except, `_NoOpSpan` yielded. The `return` after `yield _NoOpSpan()` prevents fall-through to the `try: yield span` block.
- `span.end()` exception → caught in the `finally`, logged at DEBUG. The inner exception does not propagate; the outer try-block's context (the tool body) is unaffected.
- Generator-based context managers in Python guarantee that the `finally` block runs when the `with` block exits by any means (normal return, exception, `StopAsyncIteration`). Since these are synchronous `@contextlib.contextmanager` generators wrapping async tool bodies through `with`, this is correct — async code calling `with tool_span(...) as span:` uses the synchronous context-manager protocol, which is fine.

**One subtle point worth confirming**: `tool_span` is a synchronous `@contextlib.contextmanager`, but the tool handlers in `tools.py` are `async def`. Using a synchronous context manager with `with` (not `async with`) inside an `async def` is valid Python — the context manager's `__enter__`/`__exit__` are called synchronously on the event loop thread. This is correct and matches how PostHog's `analytics.capture` (also sync) is already used in the same functions.

**Verdict**: Fail-soft is correctly implemented on both sides. No path through either helper can raise and propagate to the caller.

### 2. Secret hygiene

No API key leak found in the runtime or CI surface within the diff. Specifically:

- `logger.info("Braintrust runtime logger initialized for project %r", project)` — logs the project name only, not the key.
- `logger.warning("Failed to initialize Braintrust runtime logger: %s", exc)` — exception stringification could theoretically include the key if the SDK's exception includes it in its message, but that is SDK-side behaviour and standard practice for external SDK init failures.
- The GH Actions env block names the variable `BRAINTRUST_API_KEY` and GH Actions automatically masks secrets in runner logs. No `echo`, `print`, or repr of the key is present anywhere in the diff.
- `deploy-mcp.yml` uses `$BRAINTRUST_API_KEY` in a `--set "KEY=$VAR"` flag (see Issue 2 above for the quoting concern), but GH Actions redacts the value from step summaries when it originates from a secret.

**Verdict**: No API key leak in the diff. Issue 2 above covers the quoting concern, which is a correctness risk rather than a secret-leak risk.

### 3. Span attribute taste — PII and oversized payloads

**`test_agent_uses_kg_query_and_cites_provenance` (PR1, `test_agentic_kg_query.py`):**
- `user_msg` is logged in the span input. This is a hardcoded test string ("Which symptoms does Astragalus membranaceus treat...") — no PII.
- `final_text_preview[:500]` is the model's reply. In this E2E test, the reply is generated from KG data and does not contain user PII. Clean.

**`test_agent_uses_kg_mcp_to_ground_immune_function_question` (PR2, `test_agentic_kg_grounding.py`):**
- Same pattern. `user_msg` is a hardcoded test string. `final_text_preview[:500]` is the model's KG-grounded reply. No PII.

**Runtime tool spans (`tools.py`):**
- `kg_query` input logs `question=args.question`. This IS a user query in production. Depending on how users form questions, this could include personal health information (e.g. "I have lupus and take methotrexate — what herbs interact?"). This is intentional observability data that mirrors what PostHog already captures via `analytics.capture("kg_query_executed", {"mode": ..., "answer_length": ...})`. PostHog does NOT log the question text, however — it only logs shape metadata. **Braintrust will receive the raw question string.** This is a data governance decision, not a bug, but it's worth making explicit: Braintrust (`braintrust.dev`) will receive user queries if the key is set. The team should confirm this is within their data-handling agreement.
- `kg_hdi_check` logs `drug=args.drug, herb=args.herb` — drug names could be considered health-adjacent PII. Same category as the query text above.
- `kg_bilingual_term` logs the raw `term` value.
- Answer previews (`answer_preview: result.answer[:500]`) are KG-generated text, not user-supplied content.

**Verdict**: The `question`, `drug`, `herb`, and `term` fields logged in runtime span inputs are the most governance-sensitive. The team appears to have made a deliberate choice to match the PostHog telemetry posture. No issue is flagged here at 80+ confidence since this appears intentional, but it is documented so the decision is recorded.

### 4. Span shape consistency

- `type="tool"` for runtime spans, `type="test"` for test spans: consistent and correct.
- Span names are stable snake_case strings matching tool names (`kg_query`, `kg_traversal_herb`, etc.). Good dashboard queryability.
- Output keys across siblings:
  - Traversal tools: `chain_count`, `node_count`, `edge_count`, `seeds_resolved`. Consistent across all 6 `_make_traversal` instances (they share the same `_impl` closure).
  - `kg_query`: `answer_length`, `reference_count`, `answer_preview`. Distinct from traversals — reasonable since it's a different output shape.
  - `kg_hdi_check`: `found`, `severity`, `evidence_tier`, `citation_count`. Clean.
  - `kg_bilingual_term`: `source`, `confidence`, `english`, `chinese`, `pinyin`. Clean.
  - `kg_node_neighborhood`: `node_count`, `edge_count` — consistent with traversal naming.
- Error keys: all tools use `error=type(exc).__name__, error_message=str(exc)[:300]`. Fully consistent.

**One minor inconsistency**: traversal spans use `node_count` and `edge_count` in the output, but they also expose `raw_subgraph_node_count` / `raw_subgraph_edge_count` on the `TraversalOutput` object. The span logs the counts via `result.raw_subgraph_node_count`, not a separate recompute — the key names in the span (`node_count`) just don't match the schema field names (`raw_subgraph_node_count`). This is fine for observability but could cause confusion if someone queries the dashboard expecting the schema field name. Not flagged at 80+ confidence.

### 5. Railway `--set "KEY=$VAR"` quoting

See Issue 2 above for the full analysis. Short answer: it works for alphanumeric-plus-hyphen keys like current Braintrust API keys. It is not safe-by-construction. Switching to Railway's `--env-file` or writing to a temp file and passing via `--env-file` would be more robust. Not blocking, but worth improving in a follow-up.

### 6. Pre-existing Pyright errors in `test_agentic_kg_grounding.py`

The mentioned pre-existing Pyright errors at lines ~186/187/205/207/230 of `test_agentic_kg_grounding.py` in the *Journals* repo — this is a new file in this diff (not a pre-existing file with modifications). There are no analogous line numbers in the new file as written. The stated concern likely refers to the OpenAI SDK `msg.model_dump(exclude_none=True)` call at line 498 and `list[dict]` looseness for the `messages` list type annotation.

Looking at `messages: list[dict] = [...]` (line 470) and `messages.append(msg.model_dump(...))` (line 498): `msg` is `ChatCompletionMessage` from the OpenAI SDK; `.model_dump()` returns `dict[str, Any]`, which satisfies `dict`. No Pyright error is introduced by this diff. The errors referenced in the PR description appear to live in an older version of the file that was already present in the `test` branch — the new file starts fresh and does not import those patterns.

**Verdict**: Nothing in this diff makes pre-existing Pyright errors worse.

### 7. `_braintrust_logger.py` duplication

The duplication is correctly motivated. The two test trees (`mcp/tests/e2e/` and `shrine-diet-bioactivity/eval/tests/`) have independent `sys.path` setups. A shared location (e.g. a top-level `shared/` package) would require either: (a) installing an additional package in both test envs, or (b) manipulating `sys.path` in conftest files, both of which add fragility. The module-level docstrings document the duplication rationale and instruct readers to keep copies in sync.

**One caveat**: there are now three near-identical files, not two:
1. `mcp/tests/e2e/_braintrust_logger.py`
2. `shrine-diet-bioactivity/eval/tests/_braintrust_logger.py`
3. `Syntropy-Journals/tests/_braintrust_test_logger.py`

Files 1 and 2 are true mirrors (same code). File 3 (`_braintrust_test_logger.py`) diverges in one way: the module docstring is slightly different (references `shrine-diet-bioactivity/mcp/tests/e2e/_braintrust_logger.py` as the mirror target, rather than the eval copy). The docstring of file 1 still says "keep both copies in sync" (implying two copies), but there are now three. This is a documentation-accuracy issue that could cause the third copy to drift. Not flagged at 80+ confidence as a bug, but worth updating file 1's docstring to mention the Journals copy.

### 8. Unit test coverage of the new tracing helpers

**Honest take**: the helpers are ~80-line thin wrappers with one interesting code path: the `_INIT_ATTEMPTED` singleton. The production-critical property is fail-soft under every exception. The existing integration tests (`test_milvus_vectorstore.py`, `test_kg_mcp_live_contract.py`) and the E2E tests indirectly exercise the no-op path (when keys are absent in fork CI, all helpers silently return `_NoOpSpan`). The runtime path (`braintrust_runtime.py`) is exercised by every unit test in `mcp/tests/` when the env is clean.

That said, a single parametrized smoke test would close the coverage gap cleanly:

```python
# test_braintrust_helpers.py
def test_tool_span_is_noop_without_key(monkeypatch):
    monkeypatch.delenv("BRAINTRUST_API_KEY", raising=False)
    from kg_mcp.braintrust_runtime import tool_span
    with tool_span("probe", x=1) as span:
        span.log(output={"result": "ok"})
    # no exception raised = pass
```

The lack of such a test is a **mild** project-guideline gap (the common testing rules call for 80% coverage and unit tests for all new functions). However, the helpers are purely additive observability code with no branching business logic, and the fail-soft goal is validated implicitly by every CI run where `BRAINTRUST_API_KEY` is absent. This is a judgment call; the recommended approach is one smoke-test per helper to lock the no-raise contract, rather than a full parametrized suite.

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| Critical (95) | 1 | Assertions outside span context manager in `test_kg_mcp_live_contract.py` |
| Important (85) | 1 | `--set "KEY=$VAR"` shell quoting for Railway secret push |
| Quality note | 1 | Singleton `_INIT_ATTEMPTED` breaks test isolation (low practical risk, document or add reset) |
| **Total flagged** | **3** | |

**Verdict: PASS WITH FIXES**

The fail-soft tracing architecture is sound throughout both PRs. Span coverage is complete and consistent on the runtime side. The single critical issue is a one-line indentation bug in `test_kg_mcp_live_contract.py:257` that causes the two most important assertions to run outside the span's scope, undermining the stated retroactive-debugging goal for that specific test. Fix the indentation, address the Railway quoting concern in a follow-up, and these PRs are clean to merge.

**Fix priority**:
1. (Block merge) Fix assertion indentation at `test_kg_mcp_live_contract.py:257–262`.
2. (Follow-up, pre-next-production-deploy) Switch `railway variables --set "KEY=$VAR"` to Railway's `--env-file` or a `printf '%s'`-safe pattern.
3. (Non-blocking) Add smoke tests for both `tool_span` (PR1) and `bt_span` (PR2) no-raise contracts.
4. (Non-blocking) Update `mcp/tests/e2e/_braintrust_logger.py` docstring to mention the Journals copy as a third mirror.
