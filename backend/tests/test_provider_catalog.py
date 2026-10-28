"""
Provider/model catalogue checks:
  - backend LLM_PROVIDER_DEFAULTS and frontend/src/config/providers.js agree
  - every default model is in its provider's list, no retired model IDs linger
  - LLMClient drops/renames request parameters that newer model generations reject

Run from backend/ directory:
    pytest tests/test_provider_catalog.py -v
"""

import json
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.user import LLM_PROVIDER_DEFAULTS  # noqa: E402
from app.utils import llm_client as llm_module  # noqa: E402
from app.utils.llm_client import LLMClient  # noqa: E402

_PROVIDERS_JS = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "src", "config", "providers.js"
)

# Models the vendors have shut down / retired (checked 2026-10-28); they must not
# be offered in the picker.
_RETIRED = {
    "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3", "o3-mini", "o4-mini",
    "deepseek-chat", "deepseek-reasoner",
    "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "kimi-k2-0711-preview",
    "kimi-k2-6-preview", "open-mixtral-8x7b", "open-mixtral-8x22b", "mistral-nemo",
    "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-3-pro-preview",
    "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest",
}


def _parse_providers_js():
    src = open(_PROVIDERS_JS, encoding="utf-8").read()
    result = {}
    for match in re.finditer(r"^  (\w+): \{\n(.*?)\n  \},", src, re.S | re.M):
        body = match.group(2)
        models_block = re.search(r"models: \[(.*?)\]", body, re.S).group(1)
        result[match.group(1)] = {
            "base_url": re.search(r"base_url: '([^']+)'", body).group(1),
            "models": re.findall(r"'([^']+)'", models_block),
            "default_model": re.search(r"default_model: '([^']+)'", body).group(1),
        }
    return result


def test_frontend_and_backend_catalogues_match():
    frontend = _parse_providers_js()
    assert set(frontend) == set(LLM_PROVIDER_DEFAULTS)
    for key, backend in LLM_PROVIDER_DEFAULTS.items():
        assert frontend[key]["models"] == backend["models"], key
        assert frontend[key]["base_url"] == backend["base_url"], key
        assert frontend[key]["default_model"] == backend["default_model"], key


def test_defaults_are_listed_and_nothing_retired_is_offered():
    for key, cfg in LLM_PROVIDER_DEFAULTS.items():
        assert cfg["default_model"] in cfg["models"], key
        assert len(cfg["models"]) == len(set(cfg["models"])), key
        assert not (set(cfg["models"]) & _RETIRED), (key, set(cfg["models"]) & _RETIRED)


def test_latest_generation_models_are_offered():
    models = {k: set(v["models"]) for k, v in LLM_PROVIDER_DEFAULTS.items()}
    assert {"claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"} <= models["anthropic"]
    assert "gpt-6-astra" in models["openai"]
    assert "gemini-4-argon" in models["gemini"]
    assert "deepseek-flash" in models["deepseek"]
    assert "glm-5.3" in models["glm"]
    assert "qwen3.8-max" in models["qwen"]
    assert "kimi-k3.1-pro" in models["kimi"]
    assert "MiniMax-M3" in models["minimax"]


# ---------------------------------------------------------------------------
# LLMClient request shaping
# ---------------------------------------------------------------------------

class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = types.SimpleNamespace(content="ok")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def _openai_client(provider, model):
    client = LLMClient(api_key="k", base_url="http://x", model=model, provider=provider)
    fake = _FakeCompletions()
    client.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=fake))
    return client, fake


def test_openai_reasoning_models_get_compatible_params():
    client, fake = _openai_client("openai", "gpt-6-luna")
    assert client.chat([{"role": "user", "content": "hi"}], temperature=0.7, max_tokens=4096) == "ok"
    assert "temperature" not in fake.kwargs
    assert "max_tokens" not in fake.kwargs
    assert fake.kwargs["max_completion_tokens"] == 4096
    assert fake.kwargs["reasoning_effort"] == "low"


def test_other_providers_keep_classic_params():
    for provider, model in (("openai", "gpt-4o-mini"), ("deepseek", "deepseek-v4-pro"), ("qwen", "qwen3.8-max")):
        client, fake = _openai_client(provider, model)
        client.chat([{"role": "user", "content": "hi"}], temperature=0.3, max_tokens=100)
        assert fake.kwargs["temperature"] == 0.3
        assert fake.kwargs["max_tokens"] == 100
        assert "reasoning_effort" not in fake.kwargs


def _anthropic_payload(monkeypatch, model):
    captured = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"content": [{"type": "text", "text": "ok"}]}).encode()

    def fake_urlopen(request, timeout=0):
        captured["payload"] = json.loads(request.data.decode())
        return _Resp()

    monkeypatch.setattr(llm_module.urllib.request, "urlopen", fake_urlopen)
    client = LLMClient(api_key="k", base_url="https://api.anthropic.com/v1", model=model, provider="anthropic")
    assert client.chat([{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}], temperature=0.7) == "ok"
    return captured["payload"]


def test_new_claude_models_do_not_send_sampling_params(monkeypatch):
    for model in ("claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        payload = _anthropic_payload(monkeypatch, model)
        assert "temperature" not in payload, model
        assert payload["output_config"] == {"effort": "low"}, model
    payload = _anthropic_payload(monkeypatch, "claude-opus-4-8")
    assert "temperature" not in payload and "output_config" not in payload


def test_older_claude_models_keep_temperature(monkeypatch):
    for model in ("claude-sonnet-4-6", "claude-haiku-4-5"):
        payload = _anthropic_payload(monkeypatch, model)
        assert payload["temperature"] == 0.7, model
        assert "output_config" not in payload
