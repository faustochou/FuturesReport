"""
Structured-output guard (services/structured_output_guard.apply_structured_output_guard).

Production 2026-10-30, qwen3.8-flash: in json_object mode Graphiti appends the raw
JSON Schema to the prompt; the model replied with the schema itself, Graphiti's
parse failed ("ExtractedEntities extracted_entities Field required") and the build
died. These tests reproduce that reply over HTTP through the real build wiring
(build_graphiti -> Graphiti's OpenAI-compatible client -> OpenAI SDK).

Run from backend/ directory:
    pytest tests/test_structured_output_guard.py -v
"""

import asyncio
import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graphiti_core.prompts.extract_nodes import ExtractedEntities  # noqa: E402
from graphiti_core.prompts.models import Message  # noqa: E402

from app.services import structured_output_guard as gbatch  # noqa: E402
from app.services import graphiti_factory as gf  # noqa: E402

VALID = {"extracted_entities": [{"name": "聯合國環境規劃署", "entity_type_id": 0}]}


def _completion(content):
    return httpx.Response(200, json={
        "id": "x", "object": "chat.completion", "created": 0, "model": "qwen3.8-flash",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })


def _build_with_replies(monkeypatch, replies):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return _completion(replies[min(len(bodies) - 1, len(replies) - 1)])

    real_openai = gf.AsyncOpenAI
    monkeypatch.setattr(gf, "AsyncOpenAI", lambda **kw: real_openai(
        **kw, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    monkeypatch.setattr(gf, "FalkorDB", lambda **kw: object())
    monkeypatch.setattr(gf, "FalkorDriver", lambda **kw: object())
    monkeypatch.setattr(gf, "Graphiti", lambda **kw: type("G", (), kw)())
    graphiti = gf.build_graphiti(
        {"provider": "qwen", "model": "qwen3.8-flash", "api_key": "k",
         "base_url": "https://example.invalid/compatible-mode/v1"}, "fr_guard_test")
    return graphiti.llm_client, bodies


def _ask(llm):
    return asyncio.run(llm.generate_response(
        [Message(role="system", content="extract entities"), Message(role="user", content="UNEP report")],
        response_model=ExtractedEntities,
    ))


def test_schema_echo_is_corrected_on_retry(monkeypatch):
    schema_echo = json.dumps(ExtractedEntities.model_json_schema())
    llm, bodies = _build_with_replies(monkeypatch, [schema_echo, json.dumps(VALID, ensure_ascii=False)])

    assert _ask(llm) == VALID
    assert len(bodies) == 2
    first, second = bodies
    assert gbatch.STRUCTURED_OUTPUT_RULE in first["messages"][0]["content"]
    assert gbatch.SCHEMA_ECHO_CORRECTION in second["messages"][-1]["content"]
    assert second["enable_thinking"] is False          # qwen fix still applied
    assert "Traditional Chinese" in first["messages"][0]["content"] or \
        "Simplified Chinese" in first["messages"][0]["content"]   # language directive kept


def test_valid_answer_is_a_single_request(monkeypatch):
    llm, bodies = _build_with_replies(monkeypatch, [json.dumps(VALID, ensure_ascii=False)])
    assert _ask(llm) == VALID
    assert len(bodies) == 1


def test_persistently_invalid_answer_is_returned_unchanged(monkeypatch):
    """After the retries the last answer goes back to Graphiti as before — the guard
    never turns a call into a failure on its own."""
    llm, bodies = _build_with_replies(monkeypatch, [json.dumps({"something": "else"})])
    assert _ask(llm) == {"something": "else"}
    assert len(bodies) == 3


def test_unstructured_calls_pass_through():
    class _LLM:
        def __init__(self):
            self.seen = None

        async def generate_response(self, messages, response_model=None, **kwargs):
            self.seen = messages
            return {"content": "hi"}

    llm = _LLM()
    original_messages = [Message(role="user", content="hi")]
    gbatch.apply_structured_output_guard(llm)
    assert asyncio.run(llm.generate_response(original_messages)) == {"content": "hi"}
    assert llm.seen is original_messages
