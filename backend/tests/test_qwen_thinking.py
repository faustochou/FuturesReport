"""
Qwen hybrid-thinking models (qwen3.5+ incl. qwen3.8-flash) think by default, which
made every graph-build call take minutes (production, 2026-10-30). The graph
build's OpenAI-compatible client must send enable_thinking=false for them —
verified here on the real request body via an httpx mock transport.

Run from backend/ directory:
    pytest tests/test_qwen_thinking.py -v
"""

import asyncio
import json
import os
import sys

import httpx
import pytest
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graphiti_core.prompts.models import Message  # noqa: E402

from app.services import graphiti_factory as gf  # noqa: E402


class _Answer(BaseModel):
    ok: bool


def _run(monkeypatch, provider, model):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "{\"ok\": true}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    real = gf.AsyncOpenAI
    monkeypatch.setattr(gf, "AsyncOpenAI", lambda **kw: real(
        **kw, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    llm, _ = gf._build_llm_and_embedder(provider, "test-key", model, "https://example.invalid/compatible-mode/v1")
    result = asyncio.run(llm.generate_response(
        [Message(role="system", content="s"), Message(role="user", content="u")], response_model=_Answer,
    ))
    assert result == {"ok": True}
    assert seen["path"].endswith("/chat/completions")
    return seen["body"]


@pytest.mark.parametrize("model", ["qwen3.8-flash", "qwen3.7-plus", "qwen3.8-max", "qwen-plus"])
def test_qwen_graph_build_requests_disable_thinking(monkeypatch, model):
    body = _run(monkeypatch, "qwen", model)
    assert body["enable_thinking"] is False


@pytest.mark.parametrize("provider,model", [
    ("qwen", "qwen3.8-2.4t-a95b"),        # thinking-only: the switch would be rejected
    ("qwen", "qwen3-235b-a22b-thinking-2507"),
    ("deepseek", "deepseek-v4-pro"),      # other providers don't know this parameter
])
def test_thinking_switch_is_not_sent_where_it_does_not_apply(monkeypatch, provider, model):
    body = _run(monkeypatch, provider, model)
    assert "enable_thinking" not in body
