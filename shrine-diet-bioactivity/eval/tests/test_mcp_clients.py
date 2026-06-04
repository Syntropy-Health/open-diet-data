import pytest
from unittest.mock import MagicMock

pytestmark = [pytest.mark.unit]


def test_build_mcp_client_returns_callable_with_call_tool(monkeypatch):
    monkeypatch.setenv("KG_MCP_E2E_URL", "https://kg-mcp-test.up.railway.app")
    monkeypatch.setenv("KG_MCP_API_KEY", "test-key")
    from eval.mcp_clients import build_mcp_client  # type: ignore[import-not-found]
    c = build_mcp_client()
    assert hasattr(c, "call_tool")


def test_call_tool_extracts_span_id_from_response_payload():
    from eval.mcp_clients import MCPClient  # type: ignore[import-not-found]
    mock_session = MagicMock()
    # initialize response (no SSE)
    init_resp = MagicMock(
        status_code=200,
        text='{"jsonrpc":"2.0","id":1,"result":{"capabilities":{}}}',
        headers={"mcp-session-id": "sess-1"},
    )
    init_resp.raise_for_status = MagicMock(return_value=None)
    # notifications/initialized response (empty)
    notif_resp = MagicMock(status_code=200, text="", headers={})
    # tools/call response with SSE; bt_span_id is inside the payload JSON (PR #92 / f4182b8)
    call_resp = MagicMock(
        status_code=200,
        text='data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{\\"entities\\":[{\\"id\\":\\"x\\"}],\\"bt_span_id\\":\\"span-from-server\\"}"}],"isError":false}}\n',
        headers={},
    )
    call_resp.raise_for_status = MagicMock(return_value=None)
    mock_session.post.side_effect = [init_resp, notif_resp, call_resp]

    client = MCPClient(url="http://x", token="t", session=mock_session)
    result = client.call_tool(tool="kg_query", args={"question": "q", "mode": "hybrid"})
    assert result["_bt_span_id"] == "span-from-server"
    assert result["entities"] == [{"id": "x"}]
