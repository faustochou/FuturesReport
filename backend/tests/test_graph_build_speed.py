"""
Graph-build reliability and speed fixes (2026-10-29 incident: a build stalled
for over an hour at chunk 107/1019 with no error):

  - LLM / embedding clients carry a request timeout (google-genai has none by default)
  - chunks are ingested with Graphiti add_episode_bulk in batches, with a watchdog
  - per-request graph drivers are closed (each graph-data poll leaked a FalkorDB pool)
  - tasks interrupted by a restart are marked failed instead of "processing" forever
  - a project stuck in graph_building after a restart is reset so it can be rebuilt

Run from backend/ directory:
    pytest tests/test_graph_build_speed.py -v
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import types
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_graphspeed_")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-graph-build-speed"
os.environ["FLASK_DEBUG"] = "False"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import graph_builder as gb  # noqa: E402
from app.services import graphiti_factory as gf  # noqa: E402
from app.utils import zep_paging  # noqa: E402


# ---------------------------------------------------------------------------
# Request timeouts
# ---------------------------------------------------------------------------

def test_gemini_llm_and_embedder_share_a_client_with_timeout():
    llm, embedder = gf._build_llm_and_embedder("gemini", "test-key", "gemini-3.5-flash", "")
    assert llm.client is embedder.client
    opts = llm.client._api_client._http_options
    assert opts.timeout == gf.LLM_REQUEST_TIMEOUT_SECONDS * 1000
    assert opts.retry_options.attempts == gf.LLM_HTTP_RETRY_ATTEMPTS


def test_openai_compatible_clients_share_a_client_with_timeout():
    llm, embedder = gf._build_llm_and_embedder("qwen", "test-key", "qwen3.8-max", "https://example.invalid/v1")
    assert llm.client is embedder.client
    assert llm.client.timeout == gf.LLM_REQUEST_TIMEOUT_SECONDS
    assert llm.client.max_retries == gf.LLM_HTTP_RETRY_ATTEMPTS - 1


class _SlowHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # never answers in time
        time.sleep(5)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_genai_async_request_actually_times_out():
    """The fix relies on google-genai honouring HttpOptions.timeout on the async
    path Graphiti uses; prove it against a server that never answers in time."""
    from google import genai
    from google.genai import types as genai_types

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = genai.Client(
            api_key="test-key",
            http_options=genai_types.HttpOptions(
                base_url=f"http://127.0.0.1:{server.server_address[1]}",
                timeout=500,
                retry_options=genai_types.HttpRetryOptions(attempts=1),
            ),
        )
        started = time.monotonic()
        with pytest.raises(Exception):
            asyncio.run(client.aio.models.generate_content(model="gemini-3.5-flash", contents="hi"))
        assert time.monotonic() - started < 4
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# Bulk ingestion + watchdog + driver close
# ---------------------------------------------------------------------------

class _FakeDriver:
    def __init__(self):
        self.closed = 0

    async def close(self):
        self.closed += 1


class _FakeGraphiti:
    def __init__(self, delay=0.0):
        self.driver = _FakeDriver()
        self.batches = []
        self.delay = delay

    async def build_indices_and_constraints(self):
        pass

    async def add_episode_bulk(self, raw_episodes, group_id=None, **kwargs):
        self.batches.append([ep.name for ep in raw_episodes])
        await asyncio.sleep(self.delay)
        return types.SimpleNamespace(
            episodes=[types.SimpleNamespace(uuid=f"uuid-{ep.name}") for ep in raw_episodes]
        )


def _service():
    return gb.GraphBuilderService({"provider": "gemini", "model": "m", "api_key": "k", "base_url": ""})


def test_chunks_are_ingested_in_bulk_batches(monkeypatch):
    fake = _FakeGraphiti()
    monkeypatch.setattr(gb, "build_graphiti", lambda cfg, gid: fake)
    monkeypatch.setattr(gb, "GRAPH_BULK_BATCH_SIZE", 10)
    progress = []

    uuids = _service().add_text_batches(
        "fr_test", [f"chunk text {i}" for i in range(25)],
        progress_callback=lambda msg, ratio: progress.append(ratio),
    )

    assert [len(b) for b in fake.batches] == [10, 10, 5]
    assert fake.batches[2][-1] == "fr_test_chunk_24"
    assert len(uuids) == 25
    assert progress == [10 / 25, 20 / 25, 1.0]
    assert fake.driver.closed == 1


def test_stuck_batch_fails_instead_of_hanging(monkeypatch):
    fake = _FakeGraphiti(delay=10)
    monkeypatch.setattr(gb, "build_graphiti", lambda cfg, gid: fake)
    monkeypatch.setattr(gb, "GRAPH_BULK_BATCH_TIMEOUT", 0.3)

    started = time.monotonic()
    with pytest.raises(RuntimeError):
        _service().add_text_batches("fr_test", ["a", "b"])
    assert time.monotonic() - started < 5
    assert fake.driver.closed == 1


def test_fetch_nodes_and_edges_can_close_its_driver(monkeypatch):
    async def _empty(*args, **kwargs):
        return []

    monkeypatch.setattr(zep_paging, "_fetch_all_nodes_async", _empty)
    monkeypatch.setattr(zep_paging, "_fetch_all_edges_async", _empty)
    driver = _FakeDriver()

    zep_paging.fetch_nodes_and_edges(driver, "fr_test")
    assert driver.closed == 0
    zep_paging.fetch_nodes_and_edges(driver, "fr_test", close_driver=True)
    assert driver.closed == 1


def test_graph_data_reads_close_the_driver(monkeypatch):
    fake = _FakeGraphiti()
    monkeypatch.setattr(gb, "build_graphiti", lambda cfg, gid: fake)
    monkeypatch.setattr(gb, "enforce_embedding_consistency", lambda cfg, gid: None)

    async def _empty(*args, **kwargs):
        return []

    monkeypatch.setattr(zep_paging, "_fetch_all_nodes_async", _empty)
    monkeypatch.setattr(zep_paging, "_fetch_all_edges_async", _empty)

    data = _service().get_graph_data("fr_test")
    assert data["node_count"] == 0
    assert fake.driver.closed == 1


# ---------------------------------------------------------------------------
# Restart recovery
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_task_manager(tmp_path, monkeypatch):
    from app.models import task as task_module

    monkeypatch.setattr(task_module.TaskManager, "TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.setattr(task_module.TaskManager, "_instance", None)
    yield task_module
    task_module.TaskManager._instance = None


def _write_task(tasks_dir, task_id, status):
    os.makedirs(tasks_dir, exist_ok=True)
    now = datetime.now().isoformat()
    with open(os.path.join(tasks_dir, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump({
            "task_id": task_id, "task_type": "build", "status": status,
            "created_at": now, "updated_at": now, "progress": 23, "message": "sending 106/1019",
        }, f)


def test_restart_marks_interrupted_tasks_failed(fresh_task_manager):
    tm_cls = fresh_task_manager.TaskManager
    _write_task(tm_cls.TASKS_DIR, "t-running", "processing")
    _write_task(tm_cls.TASKS_DIR, "t-done", "completed")

    tm = tm_cls()
    assert tm.get_task("t-running").status == fresh_task_manager.TaskStatus.FAILED
    assert tm.get_task("t-running").error
    assert tm.get_task("t-done").status == fresh_task_manager.TaskStatus.COMPLETED
    with open(os.path.join(tm_cls.TASKS_DIR, "t-running.json"), encoding="utf-8") as f:
        assert json.load(f)["status"] == "failed"


@pytest.fixture
def client(tmp_path, monkeypatch, fresh_task_manager):
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-graph-build-speed"
    from app import create_app
    from app.models.project import ProjectManager

    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    application = create_app()
    application.config["TESTING"] = True
    return application.test_client()


def _stuck_project(task_id):
    from app.models.project import ProjectManager, ProjectStatus

    project = ProjectManager.create_project("stuck")
    project.status = ProjectStatus.GRAPH_BUILDING
    project.graph_id = "fr_partial"
    project.graph_build_task_id = task_id
    ProjectManager.save_project(project)
    return project.project_id


def test_orphaned_build_is_reset_so_it_can_be_rebuilt(client, monkeypatch):
    import app.api.graph as graph_api

    deleted = []
    monkeypatch.setattr(graph_api, "delete_graph_by_id", deleted.append)
    project_id = _stuck_project("task-that-no-longer-exists")

    data = client.get(f"/api/graph/project/{project_id}").get_json()["data"]
    assert data["status"] == "ontology_generated"
    assert data["graph_id"] is None
    assert data["graph_build_task_id"] is None
    assert deleted == ["fr_partial"]


def test_running_build_is_left_alone(client, monkeypatch):
    import app.api.graph as graph_api
    from app.models.task import TaskManager, TaskStatus

    deleted = []
    monkeypatch.setattr(graph_api, "delete_graph_by_id", deleted.append)
    tm = TaskManager()
    task_id = tm.create_task("build")
    tm.update_task(task_id, status=TaskStatus.PROCESSING)
    project_id = _stuck_project(task_id)

    data = client.get(f"/api/graph/project/{project_id}").get_json()["data"]
    assert data["status"] == "graph_building"
    assert data["graph_id"] == "fr_partial"
    assert deleted == []


def teardown_module(module):
    try:
        os.unlink(_db_path)
    except OSError:
        pass
