import pytest
from unittest.mock import MagicMock

pytestmark = [pytest.mark.unit]


def test_executor_runs_single_call_plan_and_returns_span_ids():
    from eval.baselines.retrieval_executor import RetrievalExecutor  # type: ignore[import-not-found]

    fake_mcp = MagicMock()
    fake_mcp.call_tool.return_value = {
        "entities": [{"id": "duke:CURCUMIN", "name": "Curcumin"}],
        "_bt_span_id": "span-abc",
    }

    executor = RetrievalExecutor(mcp_client=fake_mcp)
    plan = [{"tool": "semantic-search", "args": {"query": "turmeric", "top_k": 1}}]
    result = executor.execute(plan, bindings={})

    assert result.chains == [
        {"entities": [{"id": "duke:CURCUMIN", "name": "Curcumin"}], "_bt_span_id": "span-abc"}
    ]
    assert result.bt_span_ids == ["span-abc"]


def test_executor_templates_prev_into_later_calls():
    from eval.baselines.retrieval_executor import RetrievalExecutor  # type: ignore[import-not-found]

    fake_mcp = MagicMock()
    fake_mcp.call_tool.side_effect = [
        {"entities": [{"id": "duke:CURCUMIN"}], "_bt_span_id": "s1"},
        {"chains": [["duke:CURCUMIN", "TARGET-X"]], "_bt_span_id": "s2"},
    ]
    executor = RetrievalExecutor(mcp_client=fake_mcp)
    plan = [
        {"tool": "semantic-search", "args": {"query": "{{ seed }}", "top_k": 1}},
        {"tool": "get-subgraph", "args": {"start": "{{ prev.entities[0].id }}"}, "depth": 1},
    ]
    result = executor.execute(plan, bindings={"seed": "turmeric"})

    # Verify the second call received the resolved id, not the raw template
    call_args = fake_mcp.call_tool.call_args_list[1]
    assert call_args.kwargs["args"]["start"] == "duke:CURCUMIN"
    assert result.bt_span_ids == ["s1", "s2"]


def test_executor_returns_empty_chain_on_call_failure():
    from eval.baselines.retrieval_executor import RetrievalExecutor  # type: ignore[import-not-found]

    fake_mcp = MagicMock()
    fake_mcp.call_tool.side_effect = RuntimeError("gateway 503")
    executor = RetrievalExecutor(mcp_client=fake_mcp)
    plan = [{"tool": "semantic-search", "args": {"query": "x"}}]
    result = executor.execute(plan, bindings={})

    assert result.chains == []
    assert "gateway 503" in result.error
    assert result.bt_span_ids == []
