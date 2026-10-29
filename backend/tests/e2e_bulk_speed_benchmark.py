"""
Speed + dedupe-quality benchmark for the bulk graph build against a REAL
FalkorDB, using a fake LLM with a fixed per-call latency (no API key, no cost).
Not collected by pytest; run next to a FalkorDB:

    FALKORDB_HOST=<host> FAKE_LLM_LATENCY=1.0 BENCH_CHUNKS=250 \
        python tests/e2e_bulk_speed_benchmark.py

Compares
  old: Graphiti, batch 10, 6 concurrent                 (previous settings)
  new: BatchDedupGraphiti, batch 100, 100 concurrent    (current settings)
on the same synthetic document. Each chunk mentions a shared entity, one of two
aliases of the same organisation ("UNEP" / its full name, alternating) and four
chunk-unique entities, so the run also measures how many alias duplicates
survive (dedupe quality) and how the in-batch work scales with batch size.
"""

import ast
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import uuid

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from falkordb import FalkorDB as SyncFalkorDB  # noqa: E402
from falkordb.asyncio import FalkorDB  # noqa: E402
from graphiti_core import Graphiti  # noqa: E402
from graphiti_core import helpers as graphiti_helpers  # noqa: E402
from graphiti_core.embedder.client import EmbedderClient  # noqa: E402
from graphiti_core.llm_client.client import LLMClient  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # noqa: E402

from app.services import graph_builder as gb  # noqa: E402
from app.services.graphiti_batch import (  # noqa: E402
    AdaptiveConcurrencyLimiter, BatchDedupGraphiti, ConcurrentGeminiEmbedder, ThrottledFalkorDriver,
    apply_rate_limit_handling,
)
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig  # noqa: E402
from app.services.graphiti_factory import GRAPHITI_EMBEDDING_DIM, NoOpRerankerClient  # noqa: E402

HOST = os.environ.get("FALKORDB_HOST", "localhost")
PORT = int(os.environ.get("FALKORDB_PORT", "6379"))
LATENCY = float(os.environ.get("FAKE_LLM_LATENCY", "1.0"))
# per-request latency of the (simulated) Gemini embedding API; 0 = instant fake embedder
EMBED_LATENCY = float(os.environ.get("FAKE_EMBED_LATENCY", "0.2"))
MODES = os.environ.get("BENCH_MODES", "new,old").split(",")
CHUNKS = int(os.environ.get("BENCH_CHUNKS", "250"))
FULL, ACRONYM, SHARED = "United Nations Environment Programme", "UNEP", "Alpha Institute"
ALIASES = {ACRONYM: FULL}
MARK = re.compile(r"MENTIONS\[(.*?)\]END")


def unique_name(chunk, k):
    return "Entity " + hashlib.md5(f"{chunk}-{k}".encode()).hexdigest()[:10]


def make_chunks(n):
    out = []
    for i in range(n):
        names = [SHARED, ACRONYM if i % 2 else FULL] + [unique_name(i, k) for k in range(4)]
        out.append(f"Section {i} of the report discusses several organisations. MENTIONS[{'|'.join(names)}]END")
    return out


def _minimal(schema, defs):
    if "$ref" in schema:
        return _minimal(defs[schema["$ref"].split("/")[-1]], defs)
    if "anyOf" in schema:
        if any(s.get("type") == "null" for s in schema["anyOf"]):
            return None
        return _minimal(schema["anyOf"][0], defs)
    kind = schema.get("type")
    if kind == "object":
        return {k: _minimal(v, defs) for k, v in schema.get("properties", {}).items() if k in schema.get("required", [])}
    return {"string": "", "integer": -1, "number": 0, "boolean": False, "array": []}.get(kind)


class FakeLLM(LLMClient):
    def __init__(self):
        super().__init__(LLMConfig(api_key="fake", model="fake", small_model="fake"))
        self.calls = 0

    async def _generate_response(self, messages, response_model=None, max_tokens=0, model_size=None):
        self.calls += 1
        await asyncio.sleep(LATENCY)
        name = response_model.__name__ if response_model else ""
        text = "\n".join(m.content for m in messages)
        marks = MARK.findall(text)
        current = marks[-1].split("|") if marks else []
        if name == "ExtractedEntities":
            return {"extracted_entities": [{"name": n, "entity_type_id": 0} for n in current]}
        if name == "ExtractedEdges" and len(current) >= 2:
            schema = response_model.model_json_schema()
            edge = _minimal(schema["$defs"]["Edge"], schema["$defs"])
            # each chunk relates its own entity to the shared one (realistic fan-out,
            # instead of every chunk adding a fact to the same node pair)
            edge.update(source_entity_name=current[2], target_entity_name=current[0],
                        relation_type="WORKS_WITH", fact=f"{current[2]} works with {current[0]}")
            return {"edges": [edge]}
        if name == "NodeResolutions":
            user = messages[-1].content
            entities = json.loads(re.search(r"<ENTITIES>\s*(.*?)\s*</ENTITIES>", user, re.S).group(1))
            existing = json.loads(re.search(r"<EXISTING ENTITIES>\s*(.*?)\s*</EXISTING ENTITIES>", user, re.S).group(1))
            out = []
            for e in entities:
                canon = ALIASES.get(e["name"], e["name"])
                match = next((c["candidate_id"] for c in existing
                              if ALIASES.get(c["name"], c["name"]) == canon), -1)
                out.append({"id": e["id"], "name": e["name"], "duplicate_candidate_id": match})
            return {"entity_resolutions": out}
        if name == "EdgeDuplicate":
            # like a real model: a NEW FACT identical to an EXISTING FACT is a duplicate
            user = messages[-1].content
            section = re.search(r"<EXISTING FACTS>\s*(.*?)\s*</EXISTING FACTS>", user, re.S)
            new_fact = re.search(r"<NEW FACT>\s*(.*?)\s*</NEW FACT>", user, re.S)
            try:
                existing = ast.literal_eval(section.group(1)) if section else []
            except (ValueError, SyntaxError):
                existing = []
            new_text = new_fact.group(1) if new_fact else ""
            dups = [e["idx"] for e in existing
                    if isinstance(e, dict) and e.get("fact") and e["fact"] in new_text]
            return {"duplicate_facts": dups, "contradicted_facts": []}
        if response_model is None:
            return {"content": ""}
        schema = response_model.model_json_schema()
        return _minimal(schema, schema.get("$defs", {}))


class FakeGenaiEmbedClient:
    """Stands in for google-genai's client.aio.models.embed_content with a fixed
    per-request latency, so the real Graphiti/our Gemini embedder code paths run."""

    def __init__(self):
        self.aio = self
        self.models = self
        self.requests = 0

    async def embed_content(self, model, contents, config):
        from types import SimpleNamespace
        self.requests += 1
        await asyncio.sleep(EMBED_LATENCY)
        # Graphiti's search passes create(input_data=[query]) -> contents=[[query]]
        texts = [" ".join(map(str, c)) if isinstance(c, (list, tuple)) else str(c) for c in contents]
        return SimpleNamespace(embeddings=[SimpleNamespace(values=FakeEmbedder()._vec(t)) for t in texts])


class FakeEmbedder(EmbedderClient):
    """Aliases share a vector; unrelated names are random (near-orthogonal)."""

    def _vec(self, text):
        key = ALIASES.get(text, text)
        rng = np.random.default_rng(int(hashlib.md5(key.encode()).hexdigest()[:8], 16))
        v = rng.standard_normal(GRAPHITI_EMBEDDING_DIM)
        return (v / np.linalg.norm(v)).tolist()

    async def create(self, input_data):
        return self._vec(input_data if isinstance(input_data, str) else str(input_data))

    async def create_batch(self, input_data_list):
        return [self._vec(t) for t in input_data_list]


def run(mode):
    graph_id = f"fr_bench_{mode}_{uuid.uuid4().hex[:8]}"
    llm = FakeLLM()
    embed_client = FakeGenaiEmbedClient()
    # "seqembed": current settings but graphiti-core's sequential Gemini embedder
    new = mode in ("new", "seqembed")
    max_coroutines = 100 if new else 6

    def build(cfg, gid=None):
        # both modes use the query throttle: without it the old settings overflow
        # FalkorDB's queue too (nested semaphore_gather calls multiply concurrency)
        driver = ThrottledFalkorDriver(falkor_db=FalkorDB(host=HOST, port=PORT, socket_connect_timeout=10,
                                               socket_timeout=60), database=gid or "default_db")
        cls = BatchDedupGraphiti if new else Graphiti
        client = llm
        if new:
            apply_rate_limit_handling(client, AdaptiveConcurrencyLimiter(max_coroutines))
        graphiti_helpers.SEMAPHORE_LIMIT = max_coroutines if new else 20  # graphiti default for old
        if EMBED_LATENCY:
            config = GeminiEmbedderConfig(api_key="fake", embedding_model="gemini-embedding-001",
                                          embedding_dim=GRAPHITI_EMBEDDING_DIM)
            emb_cls = ConcurrentGeminiEmbedder if mode == "new" else GeminiEmbedder  # graphiti's: 1 item, sequential
            embedder = emb_cls(config=config, client=embed_client)
        else:
            embedder = FakeEmbedder()
        return cls(graph_driver=driver, llm_client=client, embedder=embedder,
                   cross_encoder=NoOpRerankerClient(), max_coroutines=max_coroutines)

    gb.build_graphiti = build
    gb.GRAPH_BULK_BATCH_SIZE = 100 if new else 10
    service = gb.GraphBuilderService({"provider": "gemini", "model": "fake", "api_key": "fake", "base_url": ""})

    started = time.monotonic()
    service.add_text_batches(graph_id, make_chunks(CHUNKS))
    elapsed = time.monotonic() - started

    g = SyncFalkorDB(host=HOST, port=PORT).select_graph(graph_id)
    names = [r[0] for r in g.query("MATCH (n:Entity) RETURN n.name").result_set]
    alias_nodes = sum(1 for n in names if n in (FULL, ACRONYM))
    shared_nodes = sum(1 for n in names if n == SHARED)
    expected_unique = 4 * CHUNKS
    unique_nodes = sum(1 for n in names if n.startswith("Entity "))
    episodes = g.query("MATCH (e:Episodic) RETURN count(e)").result_set[0][0]
    edges = g.query("MATCH ()-[r:RELATES_TO]->() RETURN count(r)").result_set[0][0]
    g.delete()
    return {
        "mode": mode, "seconds": round(elapsed, 1), "llm_calls": llm.calls,
        "embed_requests": embed_client.requests,
        "llm_rounds_equiv": round(elapsed / LATENCY, 1) if LATENCY else None,
        "episodes": episodes, "relates_to_edges": edges, "alias_nodes(ideal 1)": alias_nodes, "shared_nodes(ideal 1)": shared_nodes,
        f"unique_nodes(ideal {expected_unique})": unique_nodes,
    }


if __name__ == "__main__":
    print(f"chunks={CHUNKS} fake latency per LLM call={LATENCY}s")
    print(f"embedding request latency={EMBED_LATENCY}s modes={MODES}", flush=True)
    if MODES != ["new", "old"]:
        for m in MODES:
            print(run(m), flush=True)
        print("BENCH OK (custom modes)")
        raise SystemExit(0)
    new = run("new")
    print(new, flush=True)
    if "old" not in MODES:
        assert new["episodes"] == CHUNKS and new["alias_nodes(ideal 1)"] == 1
        print("BENCH OK (new only)")
        raise SystemExit(0)
    old = run("old")
    print(old, flush=True)
    print(f"speedup x{old['seconds'] / new['seconds']:.1f}")
    assert new["episodes"] == CHUNKS
    assert new["alias_nodes(ideal 1)"] == 1 and new["shared_nodes(ideal 1)"] == 1
    assert new["alias_nodes(ideal 1)"] <= old["alias_nodes(ideal 1)"], "new mode must not dedupe worse"
    print("BENCH OK")
