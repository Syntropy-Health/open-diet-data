import pytest
from unittest.mock import MagicMock, patch

pytestmark = [pytest.mark.unit]


def test_cerebras_client_uses_correct_base_url(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    with patch("eval.llm_clients.cerebras.OpenAI") as mock_oai:
        from eval.llm_clients.cerebras import build_cerebras_client  # type: ignore[import-not-found]
        build_cerebras_client()
        mock_oai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.cerebras.ai/v1",
        )


def test_cerebras_client_default_model_is_qwen3_235b(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    from eval.llm_clients.cerebras import CEREBRAS_DEFAULT_MODEL  # type: ignore[import-not-found]
    assert CEREBRAS_DEFAULT_MODEL == "qwen-3-235b-instruct"


def test_cerebras_client_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    from eval.llm_clients.cerebras import build_cerebras_client  # type: ignore[import-not-found]
    with pytest.raises(RuntimeError, match="CEREBRAS_API_KEY"):
        build_cerebras_client()


def test_cerebras_chat_completion_forwards_args(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="OK"))]
    )
    with patch("eval.llm_clients.cerebras.OpenAI", return_value=mock_client):
        from eval.llm_clients.cerebras import (  # type: ignore[import-not-found]
            CEREBRAS_DEFAULT_MODEL,
            build_cerebras_client,
        )
        c = build_cerebras_client()
        r = c.chat.completions.create(
            model=CEREBRAS_DEFAULT_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
        )
        assert r.choices[0].message.content == "OK"
