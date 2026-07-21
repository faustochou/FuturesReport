"""
Regression test for GraphBuilderService.add_text_batches() index-building
behavior.

Background: Stage 5 end-to-end testing against a real FalkorDB instance found
that indices are per-database (i.e. per graph_id — each graph_id maps to its
own FalkorDB database), not shared globally across the FalkorDB instance
(verified directly: `CALL DB.INDEXES()` on a graph that never had
build_indices_and_constraints() called on it returns 0 rows, while a sibling
graph that did returns 9). The original implementation used a single
process-level boolean flag (`_indices_built`) that made every graph_id after
the first one built in a given backend process silently skip index creation
forever — no error, just a quiet degradation to unindexed full scans.

Also verified directly against the same real FalkorDB instance that
build_indices_and_constraints() is idempotent: calling it twice on the same
database (including from a brand new driver instance) raised no exception
either time. graphiti-core's own FalkorDriver.execute_query() already
swallows "already indexed"-style errors internally. Given that, the fix
removes the caching flag entirely rather than replacing it with a
per-graph-id set — there is nothing worth caching.

Run from backend/ directory:
    pytest tests/test_graph_builder_indices.py -v
"""

import os
import tempfile
from typing import Dict, List, Tuple

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_graphidx_")
os.close(_db_fd)
_upload_dir = tempfile.mkdtemp(prefix="futuresreport_graphidx_uploads_")

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["UPLOAD_FOLDER"] = _upload_dir
os.environ["SECRET_KEY"] = "test-secret-key-for-graph-builder-indices"
os.environ["FLASK_DEBUG"] = "False"

import pytest  # noqa: E402

from app.services import graph_builder as graph_builder_module  # noqa: E402
from app.services.graph_builder import GraphBuilderService  # noqa: E402


class _FakeEpisode:
    def __init__(self, uuid: str):
        self.uuid = uuid


class _FakeEpisodeResult:
    def __init__(self, uuid: str):
        self.episode = _FakeEpisode(uuid)


class _FakeGraphiti:
    """Stands in for a real Graphiti instance. Records every
    build_indices_and_constraints()/add_episode() call (tagged with which
    graph_id this fake instance was built for) into a shared list, so the
    test can assert on call order/count without touching a real FalkorDB."""

    def __init__(self, graph_id: str, calls: List[Tuple[str, str]]):
        self._graph_id = graph_id
        self._calls = calls

    async def build_indices_and_constraints(self):
        self._calls.append(("build_indices", self._graph_id))

    async def add_episode(self, **kwargs):
        self._calls.append(("add_episode", self._graph_id))
        return _FakeEpisodeResult(uuid=f"episode-{self._graph_id}-{len(self._calls)}")


@pytest.fixture
def fake_llm_config() -> Dict[str, str]:
    return {"provider": "openai", "api_key": "test-key", "model": "gpt-4o-mini", "base_url": ""}


def test_add_text_batches_builds_indices_for_every_graph_id(monkeypatch, fake_llm_config):
    """Simulates the same backend process building two different graphs in a
    row (graph_a then graph_b). Both must trigger build_indices_and_constraints()
    — not just the first one, which was the actual bug found in Stage 5."""
    calls: List[Tuple[str, str]] = []

    def fake_build_graphiti(user_llm_config, graph_id=None):
        return _FakeGraphiti(graph_id, calls)

    monkeypatch.setattr(graph_builder_module, "build_graphiti", fake_build_graphiti)

    service = GraphBuilderService(user_llm_config=fake_llm_config)

    service.add_text_batches("graph_a", ["chunk one"])
    service.add_text_batches("graph_b", ["chunk two"])

    index_build_graph_ids = [graph_id for event, graph_id in calls if event == "build_indices"]
    assert index_build_graph_ids == ["graph_a", "graph_b"], (
        "expected build_indices_and_constraints() to run once for each graph_id "
        f"(the original process-level flag bug would have produced ['graph_a'] only), "
        f"got {index_build_graph_ids}"
    )


def test_add_text_batches_builds_indices_again_on_repeated_calls_for_same_graph(monkeypatch, fake_llm_config):
    """Calling add_text_batches() twice for the SAME graph_id (e.g. incremental
    writes to an existing graph) should also call build_indices_and_constraints()
    each time — confirmed idempotent against real FalkorDB, so there is no
    correctness or meaningful cost reason to special-case "already built"."""
    calls: List[Tuple[str, str]] = []

    def fake_build_graphiti(user_llm_config, graph_id=None):
        return _FakeGraphiti(graph_id, calls)

    monkeypatch.setattr(graph_builder_module, "build_graphiti", fake_build_graphiti)

    service = GraphBuilderService(user_llm_config=fake_llm_config)

    service.add_text_batches("graph_a", ["chunk one"])
    service.add_text_batches("graph_a", ["chunk two"])

    index_build_count = sum(1 for event, graph_id in calls if event == "build_indices" and graph_id == "graph_a")
    assert index_build_count == 2
