"""
Graph output follows the UI language (繁體中文 / 简体中文 / English):

  - every LLM request Graphiti makes carries a language directive for the
    current locale (entity names, summaries, facts)
  - type identifiers stay English; display names come from the ontology's
    display_name, from post-build translations, or generic fallbacks
  - /api/graph/data returns type_labels for the requesting locale

Run from backend/ directory:
    pytest tests/test_graph_localization.py -v
"""

import asyncio
import os
import sys
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_graphl10n_")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-graph-l10n"
os.environ["FLASK_DEBUG"] = "False"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graphiti_core.prompts.models import Message  # noqa: E402

from app.services import graph_localization as gl  # noqa: E402
from app.utils.locale import set_locale  # noqa: E402

ONTOLOGY = {
    "entity_types": [
        {"name": "ClimateScientist", "display_name": "氣候科學家", "description": "d", "attributes": []},
        {"name": "Person", "description": "d", "attributes": []},
    ],
    "edge_types": [
        {"name": "WORKS_FOR", "display_name": "任職於", "description": "d", "source_targets": []},
        {"name": "ADVISES", "description": "d", "source_targets": []},
    ],
}


# ---------------------------------------------------------------------------
# Language directive
# ---------------------------------------------------------------------------

class _RecordingLLM:
    def __init__(self):
        self.seen = None

    async def generate_response(self, messages, response_model=None, **kwargs):
        self.seen = messages
        return {"ok": True}


@pytest.mark.parametrize("locale,needle", [
    ("zh-TW", "Traditional Chinese"), ("zh", "Simplified Chinese"), ("en", "in English"),
])
def test_directive_names_the_ui_language(locale, needle):
    assert needle in gl.graph_language_directive(locale)


def test_directive_is_appended_to_the_system_message():
    llm = _RecordingLLM()
    gl.apply_language_directive(llm, "WRITE IN ZH-TW")
    original = [Message(role="system", content="extract entities"), Message(role="user", content="text")]

    asyncio.run(llm.generate_response(original, response_model=None))

    assert llm.seen[0].role == "system"
    assert llm.seen[0].content == "extract entities\n\nWRITE IN ZH-TW"
    assert llm.seen[1].content == "text"
    assert original[0].content == "extract entities"  # caller's list untouched


def test_directive_is_inserted_when_there_is_no_system_message():
    llm = _RecordingLLM()
    gl.apply_language_directive(llm, "WRITE IN ZH-TW")
    asyncio.run(llm.generate_response([Message(role="user", content="text")]))
    assert [m.role for m in llm.seen] == ["system", "user"]


@pytest.mark.parametrize("provider,model", [("gemini", "gemini-3.5-flash"), ("qwen", "qwen3.8-max")])
def test_build_graphiti_wires_the_directive_for_the_current_locale(provider, model, monkeypatch):
    """End of the real wiring: a Graphiti built while the build thread's locale is
    zh-TW sends the zh-TW directive with every request it makes."""
    from app.services import graphiti_factory as gf

    built = {}
    monkeypatch.setattr(gf, "FalkorDB", lambda **kw: object())
    monkeypatch.setattr(gf, "FalkorDriver", lambda **kw: object())
    monkeypatch.setattr(gf, "Graphiti", lambda **kw: built.update(kw) or type("G", (), kw)())
    build_graphiti = gf.build_graphiti

    set_locale("zh-TW")
    try:
        graphiti = build_graphiti(
            {"provider": provider, "model": model, "api_key": "k", "base_url": "https://example.invalid/v1"},
            "fr_l10n_test",
        )
    finally:
        set_locale("zh")

    captured = {}

    class _Stop(Exception):
        pass

    async def fake_generate(messages, response_model=None, max_tokens=None, model_size=None):
        # Record the first request the provider client would send, then stop
        # (the return shape differs per client, so don't fake a response).
        captured.setdefault("messages", [Message(role=m.role, content=m.content) for m in messages])
        raise _Stop()

    graphiti.llm_client._generate_response = fake_generate
    with pytest.raises(Exception):
        asyncio.run(graphiti.llm_client.generate_response(
            [Message(role="system", content="SYS"), Message(role="user", content="U")],
        ))
    system_text = captured["messages"][0].content
    assert system_text.startswith("SYS")
    assert "Traditional Chinese" in system_text


# ---------------------------------------------------------------------------
# Type display names
# ---------------------------------------------------------------------------

def test_type_labels_merge_order():
    stored = {"entity": {"ClimateScientist": "舊翻譯", "Person": "個人"}, "edge": {"ADVISES": "提供建議"}}
    labels = gl.build_type_labels(ONTOLOGY, stored, "zh-TW")
    assert labels["entity"]["ClimateScientist"] == "氣候科學家"   # ontology display_name wins
    assert labels["entity"]["Person"] == "個人"                   # stored beats generic
    assert labels["entity"]["Entity"] == "實體"                   # generic fallback
    assert labels["edge"] == {"WORKS_FOR": "任職於", "ADVISES": "提供建議"}


def test_missing_type_names_includes_relations_graphiti_invented():
    missing = gl.missing_type_names(ONTOLOGY, None, ["Entity", "ClimateScientist", "Person"],
                                    ["WORKS_FOR", "AUTHORED", "ADVISES"], "zh-TW")
    assert missing == {"entity": [], "edge": ["ADVISES", "AUTHORED"]}


class _FakeChatLLM:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    def chat_json(self, messages, temperature=0, max_tokens=0):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_translate_type_names_keeps_only_requested_keys():
    llm = _FakeChatLLM({"entity": {}, "edge": {"AUTHORED": "撰寫", "HALLUCINATED": "x", "ADVISES": "  "}})
    out = gl.translate_type_names(llm, {"entity": [], "edge": ["AUTHORED", "ADVISES"]}, "zh-TW")
    assert out == {"entity": {}, "edge": {"AUTHORED": "撰寫"}}


def test_translate_type_names_skips_english_and_survives_errors():
    llm = _FakeChatLLM(error=RuntimeError("boom"))
    assert gl.translate_type_names(llm, {"entity": [], "edge": ["AUTHORED"]}, "en") == {"entity": {}, "edge": {}}
    assert llm.calls == 0
    assert gl.translate_type_names(llm, {"entity": [], "edge": ["AUTHORED"]}, "zh") == {"entity": {}, "edge": {}}


def test_ontology_fallback_types_get_localized_display_names():
    from app.services.ontology_generator import OntologyGenerator

    set_locale("zh-TW")
    try:
        result = OntologyGenerator(llm_client=object())._validate_and_process(
            {"entity_types": [{"name": "ClimateScientist", "display_name": "氣候科學家"}], "edge_types": []}
        )
    finally:
        set_locale("zh")
    names = {e["name"]: e.get("display_name") for e in result["entity_types"]}
    assert names["ClimateScientist"] == "氣候科學家"
    assert names["Person"] == "人物"
    assert names["Organization"] == "組織"


# ---------------------------------------------------------------------------
# /api/graph/data returns type_labels
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-graph-l10n"
    from app import create_app
    from app.models.project import ProjectManager

    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    application = create_app()
    application.config["TESTING"] = True
    return application.test_client()


def test_graph_data_includes_type_labels_for_request_locale(client, monkeypatch):
    from app.models.project import ProjectManager
    from app.services.graph_builder import GraphBuilderService

    resp = client.post("/api/auth/register", json={"username": "l10n_user", "password": "l10npass123"})
    token = resp.get_json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put("/api/auth/llm-config", headers=headers,
               json={"provider": "gemini", "model": "gemini-3.8-flash", "api_key": "test-key"})

    project = ProjectManager.create_project("l10n")
    project.graph_id = "fr_l10n"
    project.ontology = ONTOLOGY
    project.type_display_names = {"entity": {}, "edge": {"ADVISES": "提供建議"}}
    ProjectManager.save_project(project)

    monkeypatch.setattr(GraphBuilderService, "get_graph_data",
                        lambda self, gid: {"graph_id": gid, "nodes": [], "edges": [], "node_count": 0, "edge_count": 0})

    data = client.get("/api/graph/data/fr_l10n", headers={**headers, "Accept-Language": "zh-TW"}).get_json()["data"]
    assert data["type_labels"]["entity"]["ClimateScientist"] == "氣候科學家"
    assert data["type_labels"]["entity"]["Entity"] == "實體"
    assert data["type_labels"]["edge"]["ADVISES"] == "提供建議"

    data_en = client.get("/api/graph/data/fr_l10n", headers={**headers, "Accept-Language": "en"}).get_json()["data"]
    assert data_en["type_labels"]["entity"]["Entity"] == "Entity"


def teardown_module(module):
    try:
        os.unlink(_db_path)
    except OSError:
        pass
