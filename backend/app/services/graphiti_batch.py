"""
Fast bulk graph builds without losing deduplication quality.

Speed comes from large add_episode_bulk() batches with high LLM concurrency:
everything inside a batch runs in parallel, so the number of sequential LLM
"rounds" drops from ~6 per 10 chunks to ~6-7 per batch.

The catch, and why this module exists: inside one batch Graphiti deduplicates
entities only with a deterministic name-similarity heuristic (MinHash) — the
LLM is only consulted against entities already in the graph from earlier
batches. With big batches, "聯合國環境規劃署" and "UNEP" mentioned in the same
batch would stay two nodes. BatchDedupGraphiti adds an LLM pass after
Graphiti's in-batch dedupe that applies Graphiti's own dedupe prompt
(dedupe_nodes.nodes) per chunk against the entities first introduced by
earlier chunks of the same batch — the same comparison a sequential build
would have made.

AdaptiveConcurrencyLimiter + apply_rate_limit_handling keep high concurrency
from turning provider 429s into failed builds: on a rate limit the allowed
concurrency halves and the request is retried with backoff; it creeps back
up after a run of successes.
"""

import asyncio
import random
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.gemini import GeminiEmbedder
from graphiti_core.llm_client.errors import RateLimitError
from graphiti_core.nodes import EntityNode, EpisodicNode
from graphiti_core.prompts import prompt_library
from graphiti_core.prompts.dedupe_nodes import NodeResolutions
from graphiti_core.utils.maintenance import dedup_helpers as _dedup_helpers

from ..utils.logger import get_logger

logger = get_logger('futuresreport.graphiti_batch')

# Dropped/reset connections and similar transport failures. google-genai's own
# retry only covers HTTP status codes, and graphiti-core's embedder has no retry
# at all, so one ReadError used to fail a whole build (production, 2026-10-29).
TRANSIENT_NETWORK_ERRORS = (httpx.TransportError, asyncio.TimeoutError, ConnectionError)
NETWORK_RETRIES = 4


async def _network_backoff(attempt: int) -> None:
    await asyncio.sleep(min(20.0, 1.0 * 2 ** attempt) + random.uniform(0, 0.5))

# ---------------------------------------------------------------------------
# MinHash signature cache
# ---------------------------------------------------------------------------
# Graphiti's in-batch name heuristic rebuilds a MinHash index over the growing
# pool of canonical entities for every new entity, recomputing the same name
# signatures over and over (profiled: ~81k signature computations for ~400
# names in one 100-chunk batch = ~150 s of pure CPU). The signature is a pure
# function of the shingle set, so memoizing it gives identical results.
_original_minhash_signature = _dedup_helpers._minhash_signature


@lru_cache(maxsize=65536)
def _cached_minhash_signature(shingles: frozenset) -> tuple:
    return _original_minhash_signature(shingles)


def _minhash_signature(shingles) -> tuple:
    return _cached_minhash_signature(frozenset(shingles))


_dedup_helpers._minhash_signature = _minhash_signature


# Candidate selection for the in-batch LLM pass (embedding similarity of names).
CANDIDATES_PER_NODE = 5
MIN_CANDIDATE_SIMILARITY = 0.45


# ---------------------------------------------------------------------------
# In-batch LLM entity deduplication
# ---------------------------------------------------------------------------

def _entity_type_description(labels: List[str], entity_types: Optional[Dict[str, Any]]) -> str:
    type_name = next((label for label in labels if label != 'Entity'), '')
    model = (entity_types or {}).get(type_name)
    return (model.__doc__ if model is not None else None) or 'Default Entity Type'


def _normalize(vectors: List[List[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


async def dedupe_nodes_within_batch(
    clients: Any,
    nodes_by_episode: Dict[str, List[EntityNode]],
    uuid_map: Dict[str, str],
    episode_context: List[Tuple[EpisodicNode, List[EpisodicNode]]],
    entity_types: Optional[Dict[str, Any]],
    max_coroutines: Optional[int] = None,
) -> Tuple[Dict[str, List[EntityNode]], Dict[str, str], int]:
    """Merge entities that Graphiti's in-batch heuristic missed. Returns the updated
    (nodes_by_episode, uuid_map, number_of_merges)."""
    # Unique canonical nodes in batch order, remembering which chunk introduced each.
    order: List[EntityNode] = []
    introduced_by: Dict[str, int] = {}
    for position, (episode, _) in enumerate(episode_context):
        for node in nodes_by_episode.get(episode.uuid, []):
            if node.uuid not in introduced_by:
                introduced_by[node.uuid] = position
                order.append(node)
    if len(order) < 2:
        return nodes_by_episode, uuid_map, 0

    embeddings = _normalize(await clients.embedder.create_batch([n.name for n in order]))
    similarity = embeddings @ embeddings.T
    index_of = {node.uuid: i for i, node in enumerate(order)}

    async def resolve_episode(position: int, episode: EpisodicNode, previous: List[EpisodicNode]):
        # This chunk's own new entities vs entities introduced by earlier chunks of the batch.
        new_nodes = [n for n in nodes_by_episode.get(episode.uuid, []) if introduced_by[n.uuid] == position]
        earlier = [i for i, n in enumerate(order) if introduced_by[n.uuid] < position]
        if not new_nodes or not earlier:
            return []

        asked: List[EntityNode] = []
        candidate_ids: List[int] = []
        for node in new_nodes:
            row = similarity[index_of[node.uuid]]
            ranked = sorted(earlier, key=lambda j: row[j], reverse=True)[:CANDIDATES_PER_NODE]
            ranked = [j for j in ranked if row[j] >= MIN_CANDIDATE_SIMILARITY]
            if ranked:
                asked.append(node)
                candidate_ids.extend(j for j in ranked if j not in candidate_ids)
        if not asked:
            return []

        candidates = [order[j] for j in candidate_ids]
        context = {
            'extracted_nodes': [
                {
                    'id': i,
                    'name': node.name,
                    'entity_type': node.labels,
                    'entity_type_description': _entity_type_description(node.labels, entity_types),
                }
                for i, node in enumerate(asked)
            ],
            'existing_nodes': [
                {
                    'candidate_id': i,
                    'name': candidate.name,
                    'entity_types': candidate.labels,
                    'summary': candidate.summary[:120] if candidate.summary else '',
                }
                for i, candidate in enumerate(candidates)
            ],
            'episode_content': episode.content,
            'previous_episodes': [
                {'content': ep.content, 'timestamp': ep.valid_at.isoformat() if ep.valid_at else None}
                for ep in previous or []
            ],
        }
        response = await clients.llm_client.generate_response(
            prompt_library.dedupe_nodes.nodes(context),
            response_model=NodeResolutions,
            prompt_name='dedupe_nodes.nodes',
        )
        merges = []
        for resolution in NodeResolutions(**response).entity_resolutions:
            if 0 <= resolution.id < len(asked) and 0 <= resolution.duplicate_candidate_id < len(candidates):
                merges.append((asked[resolution.id].uuid, candidates[resolution.duplicate_candidate_id].uuid))
        return merges

    semaphore = asyncio.Semaphore(max_coroutines or len(episode_context) or 1)

    async def bounded(*args):
        async with semaphore:
            return await resolve_episode(*args)

    results = await asyncio.gather(*[
        bounded(position, episode, previous)
        for position, (episode, previous) in enumerate(episode_context)
    ])

    # Union-find: a later entity always folds into the earlier one it duplicates.
    parent: Dict[str, str] = {}

    def root(uuid: str) -> str:
        while parent.get(uuid, uuid) != uuid:
            uuid = parent[uuid]
        return uuid

    merged = 0
    for merges in results:
        for duplicate_uuid, canonical_uuid in merges:
            a, b = root(duplicate_uuid), root(canonical_uuid)
            if a == b:
                continue
            # keep whichever was introduced first as the canonical node
            if introduced_by[a] < introduced_by[b]:
                a, b = b, a
            parent[a] = b
            merged += 1
    if not merged:
        return nodes_by_episode, uuid_map, 0

    by_uuid = {node.uuid: node for node in order}
    new_nodes_by_episode: Dict[str, List[EntityNode]] = {}
    for episode_uuid, nodes in nodes_by_episode.items():
        seen, kept = set(), []
        for node in nodes:
            canonical = by_uuid[root(node.uuid)]
            if canonical.uuid not in seen:
                seen.add(canonical.uuid)
                kept.append(canonical)
        new_nodes_by_episode[episode_uuid] = kept

    new_uuid_map = {key: root(value) for key, value in uuid_map.items()}
    for uuid in parent:
        new_uuid_map[uuid] = root(uuid)
    logger.info(f"in-batch LLM dedupe merged {merged} entities out of {len(order)}")
    return new_nodes_by_episode, new_uuid_map, merged


class BatchDedupGraphiti(Graphiti):
    """Graphiti whose bulk path adds the in-batch LLM entity dedupe pass."""

    async def _extract_and_dedupe_nodes_bulk(self, episode_context, *args, **kwargs):
        nodes_by_episode, uuid_map, extracted_edges_bulk = await super()._extract_and_dedupe_nodes_bulk(
            episode_context, *args, **kwargs
        )
        entity_types = kwargs.get('entity_types', args[2] if len(args) > 2 else None)
        nodes_by_episode, uuid_map, _ = await dedupe_nodes_within_batch(
            self.clients, nodes_by_episode, uuid_map, episode_context, entity_types,
            max_coroutines=self.max_coroutines,
        )
        return nodes_by_episode, uuid_map, extracted_edges_bulk


# ---------------------------------------------------------------------------
# Gemini embeddings: batched and concurrent
# ---------------------------------------------------------------------------

class ConcurrentGeminiEmbedder(GeminiEmbedder):
    """graphiti-core's GeminiEmbedder forces batch_size=1 for gemini-embedding-001
    (a Vertex AI limit) and then embeds strictly one item after another, so every
    create_batch() over a few hundred entities/facts became hundreds of sequential
    HTTP round trips — the slow single-connection phase seen in production
    (2026-10-29). Here batches of up to `batch_size` go out concurrently; if the
    API rejects multi-input requests (HTTP 400) we switch to single-item requests,
    still concurrently, and remember that for the rest of the build."""

    def __init__(self, *args, batch_size: int = 100, max_concurrency: int = 32, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = max(1, batch_size)
        self._max_concurrency = max(1, max_concurrency)
        self._multi_input_ok = True

    async def _embed(self, contents: List[str]) -> List[List[float]]:
        for attempt in range(NETWORK_RETRIES + 1):
            try:
                result = await self.client.aio.models.embed_content(
                    model=self.config.embedding_model,
                    contents=contents,
                    config=genai_types.EmbedContentConfig(output_dimensionality=self.config.embedding_dim),
                )
                break
            except TRANSIENT_NETWORK_ERRORS as exc:
                if attempt == NETWORK_RETRIES:
                    raise
                logger.warning(f"embedding request failed ({type(exc).__name__}), retrying")
                await _network_backoff(attempt)
        vectors = [e.values for e in (result.embeddings or [])]
        if len(vectors) != len(contents) or not all(vectors):
            raise ValueError(f"expected {len(contents)} embeddings, got {len(vectors)}")
        return vectors

    async def create_batch(self, input_data_list: List[str]) -> List[List[float]]:
        if not input_data_list:
            return []
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def bounded(contents):
            async with semaphore:
                return await self._embed(contents)

        if self._multi_input_ok and self.batch_size > 1:
            chunks = [input_data_list[i:i + self.batch_size]
                      for i in range(0, len(input_data_list), self.batch_size)]
            try:
                results = await asyncio.gather(*[bounded(c) for c in chunks])
                return [vector for chunk in results for vector in chunk]
            except genai_errors.ClientError as exc:
                if getattr(exc, "code", None) != 400:
                    raise
                logger.warning(f"multi-input embedding rejected ({exc}); using single-item requests")
                self._multi_input_ok = False

        results = await asyncio.gather(*[bounded([item]) for item in input_data_list])
        return [chunk[0] for chunk in results]


# ---------------------------------------------------------------------------
# FalkorDB query throttle
# ---------------------------------------------------------------------------

# Graphiti uses the same max_coroutines for LLM calls and graph queries. LLM calls
# can safely run ~100 wide, but FalkorDB rejects work beyond MAX_QUEUED_QUERIES
# (default 25) with "Max pending queries exceeded" — found by the 250-chunk
# benchmark. Queries get their own, lower cap: about 2x FalkorDB's worker
# threads, so excess queries wait here (no timeout) instead of queueing on the
# server, where the wait counts against the client socket timeout.
FALKORDB_MAX_CONCURRENT_QUERIES = 8
_QUEUE_FULL = "Max pending queries exceeded"


class _LoopLocalSemaphore:
    """asyncio.Semaphore recreated per event loop (each build runs in its own asyncio.run())."""

    def __init__(self, size: int):
        self.size = max(1, size)
        self._sem: Optional[asyncio.Semaphore] = None
        self._loop = None

    def get(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._sem is None or self._loop is not loop:
            self._sem, self._loop = asyncio.Semaphore(self.size), loop
        return self._sem


class _ThrottledGraph:
    """Proxy for a FalkorDB graph whose query() goes through a shared gate."""

    def __init__(self, graph: Any, gate: _LoopLocalSemaphore):
        self._graph = graph
        self._gate = gate

    def __getattr__(self, name):
        return getattr(self._graph, name)

    async def query(self, *args, **kwargs):
        # the server queue is shared with other clients and drains within seconds;
        # back off for up to ~1 minute before giving up
        attempts = 8
        for attempt in range(attempts):
            async with self._gate.get():
                try:
                    return await self._graph.query(*args, **kwargs)
                except Exception as exc:
                    # other clients (e.g. the page's graph polling) share the server queue
                    if _QUEUE_FULL not in str(exc) or attempt == attempts - 1:
                        raise
            await asyncio.sleep(min(30.0, 0.5 * 2 ** attempt))


class ThrottledFalkorDriver(FalkorDriver):
    """FalkorDriver that caps concurrent queries (see FALKORDB_MAX_CONCURRENT_QUERIES)."""

    def __init__(self, *args, max_concurrent_queries: int = FALKORDB_MAX_CONCURRENT_QUERIES,
                 _gate: Optional[_LoopLocalSemaphore] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._gate = _gate or _LoopLocalSemaphore(max_concurrent_queries)

    def _get_graph(self, graph_name):
        return _ThrottledGraph(super()._get_graph(graph_name), self._gate)

    def clone(self, database: str):
        if database == self._database:
            return self
        return ThrottledFalkorDriver(falkor_db=self.client, database=database, _gate=self._gate)


# ---------------------------------------------------------------------------
# Adaptive concurrency for provider rate limits
# ---------------------------------------------------------------------------

class AdaptiveConcurrencyLimiter:
    """Caps in-flight LLM requests; halves the cap on a rate limit, raises it by one
    after `limit` consecutive successes (AIMD)."""

    def __init__(self, max_limit: int, min_limit: int = 4):
        self.max_limit = max(1, max_limit)
        self.min_limit = max(1, min(min_limit, self.max_limit))
        self.limit = self.max_limit
        self._in_flight = 0
        self._ok_streak = 0
        self._cond: Optional[asyncio.Condition] = None
        self._loop = None

    def _condition(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self._cond is None or self._loop is not loop:
            # each build runs in its own asyncio.run(); never reuse a primitive across loops
            self._cond, self._loop, self._in_flight = asyncio.Condition(), loop, 0
        return self._cond

    async def __aenter__(self):
        cond = self._condition()
        async with cond:
            await cond.wait_for(lambda: self._in_flight < self.limit)
            self._in_flight += 1
        return self

    async def __aexit__(self, *exc):
        cond = self._condition()
        async with cond:
            self._in_flight -= 1
            cond.notify_all()
        return False

    def on_rate_limited(self) -> None:
        new_limit = max(self.min_limit, self.limit // 2)
        if new_limit < self.limit:
            logger.warning(f"LLM rate limited: concurrency {self.limit} -> {new_limit}")
        self.limit = new_limit
        self._ok_streak = 0

    def on_success(self) -> None:
        self._ok_streak += 1
        if self.limit < self.max_limit and self._ok_streak >= self.limit:
            self.limit += 1
            self._ok_streak = 0


def apply_rate_limit_handling(
    llm_client: Any,
    limiter: AdaptiveConcurrencyLimiter,
    max_retries: int = 6,
    base_delay: float = 5.0,
) -> Any:
    """Wrap generate_response: bounded by `limiter`; on RateLimitError shrink the
    limit, back off and retry instead of failing the whole build."""
    original = llm_client.generate_response

    async def generate_response(messages, *args, **kwargs):
        attempt = 0
        network_attempt = 0
        while True:
            async with limiter:
                try:
                    result = await original(messages, *args, **kwargs)
                except RateLimitError:
                    limiter.on_rate_limited()
                    attempt += 1
                    if attempt > max_retries:
                        raise
                    delay = min(60.0, base_delay * 2 ** (attempt - 1)) + random.uniform(0, 1)
                except TRANSIENT_NETWORK_ERRORS as exc:
                    # a dropped connection is not a reason to fail the whole build
                    if network_attempt >= NETWORK_RETRIES:
                        raise
                    logger.warning(f"LLM request failed ({type(exc).__name__}), retrying")
                    delay = min(20.0, 1.0 * 2 ** network_attempt) + random.uniform(0, 0.5)
                    network_attempt += 1
                else:
                    limiter.on_success()
                    return result
            await asyncio.sleep(delay)

    llm_client.generate_response = generate_response
    return llm_client
