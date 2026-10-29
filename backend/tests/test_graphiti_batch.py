"""
Fast bulk builds (services/graphiti_batch.py):
  - in-batch LLM entity dedupe merges what Graphiti's name heuristic misses
    (e.g. an acronym and the full name in the same batch), and nothing else
  - adaptive concurrency limiter + rate-limit retry

Run from backend/ directory:
    pytest tests/test_graphiti_batch.py -v
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graphiti_core.llm_client.errors import RateLimitError  # noqa: E402
from graphiti_core.nodes import EntityNode, EpisodeType, EpisodicNode  # noqa: E402

from app.services import graphiti_batch as gbatch  # noqa: E402

ALIASES = {"UNEP": "United Nations Environment Programme"}


def _episode(i):
    return EpisodicNode(
        name=f"ep{i}", group_id="g", labels=[], source=EpisodeType.text, content=f"chunk {i}",
        source_description="d", created_at=datetime.now(timezone.utc), valid_at=datetime.now(timezone.utc),
    )


def _node(name):
    return EntityNode(name=name, group_id="g", labels=["Entity"], summary="")


class _Embedder:
    """Alias pairs get identical vectors; everything else is (nearly) orthogonal."""

    async def create_batch(self, names):
        vecs = []
        for name in names:
            key = ALIASES.get(name, name)
            seed = sum(ord(c) for c in key)
            vec = [0.0] * 64
            vec[seed % 64] = 1.0
            vecs.append(vec)
        return vecs


class _AliasLLM:
    """Answers Graphiti's dedupe_nodes.nodes prompt like a careful model would:
    duplicate only when names match or are known aliases."""

    def __init__(self):
        self.calls = 0

    async def generate_response(self, messages, response_model=None, **kwargs):
        self.calls += 1
        text = messages[-1].content
        entities = json.loads(re.search(r"<ENTITIES>\s*(.*?)\s*</ENTITIES>", text, re.S).group(1))
        existing = json.loads(re.search(r"<EXISTING ENTITIES>\s*(.*?)\s*</EXISTING ENTITIES>", text, re.S).group(1))
        out = []
        for e in entities:
            canon = ALIASES.get(e["name"], e["name"])
            match = next((c["candidate_id"] for c in existing if ALIASES.get(c["name"], c["name"]) == canon), -1)
            out.append({"id": e["id"], "name": e["name"], "duplicate_candidate_id": match})
        return {"entity_resolutions": out}


class _Clients:
    def __init__(self):
        self.embedder = _Embedder()
        self.llm_client = _AliasLLM()


def test_in_batch_dedupe_merges_aliases_across_chunks_only():
    eps = [_episode(i) for i in range(3)]
    full, alpha = _node("United Nations Environment Programme"), _node("Alpha Institute")
    acronym, beta = _node("UNEP"), _node("Beta Agency")
    nodes_by_episode = {eps[0].uuid: [full, alpha], eps[1].uuid: [beta], eps[2].uuid: [acronym, alpha]}
    extracted_acronym_uuid = "extracted-acronym"
    uuid_map = {extracted_acronym_uuid: acronym.uuid}
    clients = _Clients()

    new_nodes, new_map, merged = asyncio.run(gbatch.dedupe_nodes_within_batch(
        clients, nodes_by_episode, uuid_map, [(e, []) for e in eps], None,
    ))

    assert merged == 1
    assert [n.name for n in new_nodes[eps[2].uuid]] == ["United Nations Environment Programme", "Alpha Institute"]
    assert new_map[acronym.uuid] == full.uuid               # edges pointing at the acronym get re-pointed
    assert new_map[extracted_acronym_uuid] == full.uuid     # and so do earlier mappings
    assert [n.name for n in new_nodes[eps[1].uuid]] == ["Beta Agency"]
    # one LLM call: only chunk 2 introduced a new entity with a similar earlier candidate
    assert clients.llm_client.calls == 1


def test_in_batch_dedupe_leaves_distinct_entities_alone():
    eps = [_episode(i) for i in range(2)]
    nodes_by_episode = {eps[0].uuid: [_node("Alpha Institute")], eps[1].uuid: [_node("Beta Agency")]}
    new_nodes, new_map, merged = asyncio.run(gbatch.dedupe_nodes_within_batch(
        _Clients(), nodes_by_episode, {}, [(e, []) for e in eps], None,
    ))
    assert merged == 0 and new_nodes is nodes_by_episode and new_map == {}


# ---------------------------------------------------------------------------
# Adaptive limiter + rate-limit retry
# ---------------------------------------------------------------------------

def test_limiter_caps_in_flight_requests():
    limiter = gbatch.AdaptiveConcurrencyLimiter(max_limit=3)
    state = {"now": 0, "peak": 0}

    async def work():
        async with limiter:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
            await asyncio.sleep(0.01)
            state["now"] -= 1

    async def main():
        await asyncio.gather(*[work() for _ in range(20)])

    asyncio.run(main())
    assert state["peak"] == 3


def test_rate_limits_shrink_concurrency_and_are_retried():
    limiter = gbatch.AdaptiveConcurrencyLimiter(max_limit=16, min_limit=2)

    class _Flaky:
        def __init__(self):
            self.calls = 0

        async def generate_response(self, messages, **kwargs):
            self.calls += 1
            if self.calls <= 2:
                raise RateLimitError()
            return {"ok": True}

    llm = _Flaky()
    gbatch.apply_rate_limit_handling(llm, limiter, max_retries=5, base_delay=0.01)
    assert asyncio.run(llm.generate_response([])) == {"ok": True}
    assert llm.calls == 3
    assert limiter.limit == 4  # 16 -> 8 -> 4


def test_rate_limit_gives_up_after_max_retries():
    limiter = gbatch.AdaptiveConcurrencyLimiter(max_limit=4)

    class _AlwaysLimited:
        async def generate_response(self, messages, **kwargs):
            raise RateLimitError()

    llm = _AlwaysLimited()
    gbatch.apply_rate_limit_handling(llm, limiter, max_retries=2, base_delay=0.01)
    with pytest.raises(RateLimitError):
        asyncio.run(llm.generate_response([]))


def test_limiter_recovers_after_successes():
    limiter = gbatch.AdaptiveConcurrencyLimiter(max_limit=8, min_limit=2)
    limiter.on_rate_limited()
    assert limiter.limit == 4
    for _ in range(4):
        limiter.on_success()
    assert limiter.limit == 5


# ---------------------------------------------------------------------------
# MinHash signature cache: identical results, installed where Graphiti looks
# ---------------------------------------------------------------------------

def test_minhash_cache_matches_original_and_is_installed():
    from graphiti_core.utils.maintenance import dedup_helpers

    assert dedup_helpers._minhash_signature is gbatch._minhash_signature
    for name in ["united nations environment programme", "unep", "alpha institute", "ab", ""]:
        shingles = dedup_helpers._shingles(name)
        assert gbatch._minhash_signature(shingles) == gbatch._original_minhash_signature(shingles)
        assert gbatch._minhash_signature(list(shingles)) == gbatch._original_minhash_signature(shingles)
