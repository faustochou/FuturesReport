"""
End-to-end check of the bulk graph build against a REAL FalkorDB, with a
deterministic fake LLM + embedder (no API key, no cost). Not collected by
pytest (file name doesn't start with test_); run it next to a FalkorDB:

    FALKORDB_HOST=<host> python tests/e2e_bulk_ingest_falkordb.py

Checks:
  1. GraphBuilderService.add_text_batches() ingests every chunk through
     Graphiti add_episode_bulk() in batches and the data lands in FalkorDB
     (episodes, deduplicated entities, relation edges).
  2. Repeated get_graph_data() calls (what the page polls every 10 s) do not
     leave FalkorDB connections open.
  3. delete_graph_by_id() empties the graph.
"""

import asyncio
import hashlib
import math
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from falkordb import FalkorDB as SyncFalkorDB  # noqa: E402
from falkordb.asyncio import FalkorDB  # noqa: E402
from graphiti_core import Graphiti  # noqa: E402
from graphiti_core.driver.falkordb_driver import FalkorDriver  # noqa: E402
from graphiti_core.embedder.client import EmbedderClient  # noqa: E402
from graphiti_core.llm_client.client import LLMClient  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # noqa: E402

from app.services import graph_builder as gb  # noqa: E402
from app.services.graphiti_factory import GRAPHITI_EMBEDDING_DIM, NoOpRerankerClient  # noqa: E402

HOST = os.environ.get("FALKORDB_HOST", "localhost")
PORT = int(os.environ.get("FALKORDB_PORT", "6379"))
PASSWORD = os.environ.get("FALKORDB_PASSWORD") or None
GRAPH_ID = f"fr_e2e_{uuid.uuid4().hex[:12]}"
ENTITIES = ["Alpha Institute", "Beta Agency"]


def _minimal(schema, defs):
    """Smallest value that validates against a JSON-schema fragment."""
    if "$ref" in schema:
        return _minimal(defs[schema["$ref"].split("/")[-1]], defs)
    if "anyOf" in schema:
        if any(s.get("type") == "null" for s in schema["anyOf"]):
            return None
        return _minimal(schema["anyOf"][0], defs)
    kind = schema.get("type")
    if kind == "object":
        return {
            name: _minimal(prop, defs)
            for name, prop in schema.get("properties", {}).items()
            if name in schema.get("required", [])
        }
    return {"string": "", "integer": -1, "number": 0, "boolean": False, "array": []}.get(kind)


class FakeLLM(LLMClient):
    """Every episode mentions the same two entities and one relation between them,
    so the bulk path must deduplicate them across episodes and batches."""

    def __init__(self):
        super().__init__(LLMConfig(api_key="fake", model="fake", small_model="fake"))

    async def _generate_response(self, messages, response_model=None, max_tokens=0, model_size=None):
        name = response_model.__name__ if response_model else ""
        if name == "ExtractedEntities":
            return {"extracted_entities": [{"name": n, "entity_type_id": 0} for n in ENTITIES]}
        if name == "ExtractedEdges":
            schema = response_model.model_json_schema()
            edge = _minimal(schema["$defs"]["Edge"], schema["$defs"])
            edge.update(
                source_entity_name=ENTITIES[0],
                target_entity_name=ENTITIES[1],
                relation_type="COLLABORATES_WITH",
                fact=f"{ENTITIES[0]} collaborates with {ENTITIES[1]}",
            )
            return {"edges": [edge]}
        if response_model is None:
            return {"content": ""}
        schema = response_model.model_json_schema()
        return _minimal(schema, schema.get("$defs", {}))


class FakeEmbedder(EmbedderClient):
    async def create(self, input_data):
        text = input_data if isinstance(input_data, str) else str(input_data)
        digest = hashlib.sha256(text.encode()).digest()
        vec = [digest[i % len(digest)] / 255.0 + 0.01 for i in range(GRAPHITI_EMBEDDING_DIM)]
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec]

    async def create_batch(self, input_data_list):
        return [await self.create(t) for t in input_data_list]


def fake_build_graphiti(user_llm_config, graph_id=None):
    driver = FalkorDriver(
        falkor_db=FalkorDB(host=HOST, port=PORT, password=PASSWORD,
                           socket_connect_timeout=10, socket_timeout=30),
        database=graph_id or "default_db",
    )
    return Graphiti(graph_driver=driver, llm_client=FakeLLM(), embedder=FakeEmbedder(),
                    cross_encoder=NoOpRerankerClient(), max_coroutines=6)


def connected_clients(db):
    return int(db.connection.info("clients")["connected_clients"])


def main():
    gb.build_graphiti = fake_build_graphiti
    gb.enforce_embedding_consistency = lambda cfg, gid: None
    service = gb.GraphBuilderService({"provider": "gemini", "model": "fake", "api_key": "fake", "base_url": ""})
    sync_db = SyncFalkorDB(host=HOST, port=PORT, password=PASSWORD)

    chunks = [f"Report section {i}: {ENTITIES[0]} works with {ENTITIES[1]} on coastal policy item {i}."
              for i in range(23)]
    progress = []
    uuids = service.add_text_batches(GRAPH_ID, chunks,
                                     progress_callback=lambda msg, ratio: progress.append(round(ratio, 3)))

    g = sync_db.select_graph(GRAPH_ID)
    episodes = g.query("MATCH (e:Episodic) RETURN count(e)").result_set[0][0]
    entities = g.query("MATCH (n:Entity) RETURN n.name").result_set
    edges = g.query("MATCH ()-[r:RELATES_TO]->() RETURN count(r)").result_set[0][0]
    mentions = g.query("MATCH (:Episodic)-[r:MENTIONS]->(:Entity) RETURN count(r)").result_set[0][0]
    print(f"batch size={gb.GRAPH_BULK_BATCH_SIZE} progress={progress}")
    print(f"episodes={episodes} returned_uuids={len(uuids)} entities={sorted(r[0] for r in entities)} "
          f"relates_to={edges} mentions={mentions}")
    assert episodes == len(chunks) == len(uuids), "every chunk must become an episode"
    assert progress[-1] == 1.0 and len(progress) == math.ceil(len(chunks) / gb.GRAPH_BULK_BATCH_SIZE)
    assert sorted(r[0] for r in entities) == sorted(ENTITIES), "entities must be deduplicated across batches"
    assert edges >= 1 and mentions >= len(chunks)

    before = connected_clients(sync_db)
    for _ in range(20):
        data = service.get_graph_data(GRAPH_ID)
    after = connected_clients(sync_db)
    print(f"graph data: nodes={data['node_count']} edges={data['edge_count']}; "
          f"connected clients before={before} after 20 polls={after}")
    assert data["node_count"] == 2
    assert after - before <= 1, "graph-data polling must not leak FalkorDB connections"

    gb.delete_graph_by_id(GRAPH_ID)
    left = g.query("MATCH (n) RETURN count(n)").result_set[0][0]
    print(f"after delete: nodes left={left}")
    assert left == 0
    sync_db.select_graph(GRAPH_ID).delete()
    print("E2E OK")


if __name__ == "__main__":
    main()
