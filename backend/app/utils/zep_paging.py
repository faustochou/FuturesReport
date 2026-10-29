"""Graphiti 图谱分页读取工具。

沿用原 Zep 版本的 UUID cursor 分页 + 单页重试模式（函数签名与语义保持一致，
只是数据源从 Zep Cloud API 换成 Graphiti 的 EntityNode/EntityEdge.get_by_group_ids()，
两者都用 `uuid_cursor` + `ORDER BY uuid DESC` 的游标分页，语义直接对应）。

模块名沿用 zep_paging 是为了让既有调用方（zep_entity_reader.py / zep_tools.py）
零改动地继续 import 同名函数；内部实现已完全是 Graphiti/FalkorDB。公开函数对外
仍是同步的（内部用单一 asyncio.run() 包住整个分页循环），呼叫端不需要改成 async。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from graphiti_core.driver.driver import GraphDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from graphiti_core.errors import GroupsEdgesNotFoundError
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from .logger import get_logger

logger = get_logger('futuresreport.zep_paging')

_DEFAULT_PAGE_SIZE = 100
_MAX_NODES = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0  # seconds, doubles each retry

T = TypeVar('T')


class PagedResult(list):
    """list 的輕量子類別，多一個 is_complete 旗標。

    背景：Stage 5 端到端測試對真實 FalkorDB 實測到一個引擎層級的缺陷——
    `WHERE e.uuid < $uuid` 篩選在 `uuid` 有 RANGE 索引時，沒有正確排除
    「相等」的邊界記錄（直接對純量做同樣比較則是對的，只有搭配索引掃描的
    WHERE 篩選才會錯）。用超過一頁的真實資料量驗證過兩種表現都會發生，且
    不只出現在極端的 page_size=1：
      1) 卡住不前進——下一頁一直拿回同一筆，永遠湊不到空頁結束條件。
      2) 跨頁重複——不同頁之間吐出已經收過的記錄，導致總筆數比實際多
         （生產預設的 page_size=100、230 筆資料時實測到，回傳 249 筆）。
    seen_uuids 去重（見下方 _fetch_all_nodes_async / _fetch_all_edges_async）
    同時防住這兩種情況：卡住時偵測「整頁都已看過」就停止，重複時單純把
    已看過的記錄濾掉不計入結果。但去重無法讓底層引擎補回被卡住、實際上
    永遠讀不到的那部分資料——這種情況下分頁結果仍然可能比實際總數少。

    這裡在分頁跑完後多做一次低成本的 COUNT 查詢，跟實際收集到（去重後）的
    筆數比對；不一致就把 is_complete 設成 False 並記 WARNING，讓上層有機會
    感知資料不完整（而不是默默回傳一個看似正常、實則被截斷的 list）。這是
    list 的子類別，既有呼叫端把回傳值當一般 list 用完全不用改
    （isinstance list、len()、迭代都正常）；需要感知完整性的呼叫端可以
    另外檢查 `.is_complete`。
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.is_complete = True


async def _fetch_page_with_retry(
    api_call: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    page_description: str = "page",
    **kwargs: Any,
) -> T:
    """单页请求，失败时指数退避重试。仅重试网络/IO类瞬态错误（FalkorDB/Redis 连线问题）。"""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    last_exception: Exception | None = None
    delay = retry_delay

    for attempt in range(max_retries):
        try:
            return await api_call(*args, **kwargs)
        except (ConnectionError, TimeoutError, OSError, RedisConnectionError, RedisTimeoutError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"FalkorDB {page_description} attempt {attempt + 1} failed: {str(e)[:100]}, retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                logger.error(f"FalkorDB {page_description} failed after {max_retries} attempts: {str(e)}")

    assert last_exception is not None
    raise last_exception


async def _count_nodes(driver: GraphDriver, graph_id: str) -> int | None:
    """低成本 COUNT 查詢，用來跟分頁收集到的筆數比對（見 PagedResult）。
    查詢本身失敗（例如連線問題）不應該讓整個分頁流程報錯，回傳 None 表示
    「這次無法驗證完整性」，呼叫端應該當作「跳過檢查」處理，而不是當成
    不完整。"""
    try:
        records, _, _ = await driver.execute_query(
            'MATCH (n:Entity) WHERE n.group_id IN $group_ids RETURN count(n) AS cnt',
            group_ids=[graph_id],
            routing_='r',
        )
        return int(records[0]['cnt'])
    except Exception as e:
        logger.debug(f"Node count verification query failed (skipping check): {str(e)[:150]}")
        return None


async def _count_edges(driver: GraphDriver, graph_id: str) -> int | None:
    """同 _count_nodes，但對 RELATES_TO 邊。"""
    try:
        records, _, _ = await driver.execute_query(
            'MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity) WHERE e.group_id IN $group_ids RETURN count(e) AS cnt',
            group_ids=[graph_id],
            routing_='r',
        )
        return int(records[0]['cnt'])
    except Exception as e:
        logger.debug(f"Edge count verification query failed (skipping check): {str(e)[:150]}")
        return None


async def _fetch_all_nodes_async(
    driver: GraphDriver,
    graph_id: str,
    page_size: int,
    max_items: int,
    max_retries: int,
    retry_delay: float,
) -> PagedResult:
    all_nodes: list[EntityNode] = []
    seen_uuids: set[str] = set()
    cursor: str | None = None
    page_num = 0

    while True:
        page_num += 1
        batch = await _fetch_page_with_retry(
            EntityNode.get_by_group_ids,
            driver,
            [graph_id],
            limit=page_size,
            uuid_cursor=cursor,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch nodes page {page_num} (graph={graph_id})",
        )
        if not batch:
            break

        # 去重防禦：Stage 5 端到端測試對真實 FalkorDB 實測到一個引擎層級的
        # 缺陷——`WHERE n.uuid < $uuid` 篩選在 `uuid` 有 RANGE 索引時，不會
        # 正確排除邊界值，導致跨頁邊界可能重複吐出已經收過的記錄（用超過一頁
        # 的真實資料量驗證過，不只發生在極端的 page_size=1，生產預設的
        # page_size=100 一樣會在跨頁時中招）。與其信任游標一定會正確前進，
        # 這裡改成用 seen_uuids 過濾每一頁，只保留真正沒看過的記錄。
        new_items = [n for n in batch if n.uuid not in seen_uuids]
        if not new_items:
            # 整頁都是已經收過的記錄：分頁已經卡住，不會再有新資料了，停止
            # 避免無限迴圈。
            logger.warning(
                f"Node pagination stuck (page {page_num} returned only already-seen records), "
                f"stopping at {len(all_nodes)} nodes for graph {graph_id} to avoid infinite loop"
            )
            break

        for n in new_items:
            seen_uuids.add(n.uuid)
        all_nodes.extend(new_items)

        if len(all_nodes) >= max_items:
            all_nodes = all_nodes[:max_items]
            logger.warning(f"Node count reached limit ({max_items}), stopping pagination for graph {graph_id}")
            break
        if len(batch) < page_size:
            break

        next_cursor = batch[-1].uuid
        if next_cursor is None:
            logger.warning(f"Node missing uuid field, stopping pagination at {len(all_nodes)} nodes")
            break
        cursor = next_cursor

    result = PagedResult(all_nodes)
    if len(all_nodes) < max_items:
        # 只有在沒有被 max_items 截斷的情況下比對總數才有意義——被截斷是
        # 預期行為（見上面的 warning），不是「引擎沒把資料吐完整」。
        total = await _count_nodes(driver, graph_id)
        if total is not None and total != len(all_nodes):
            result.is_complete = False
            logger.warning(
                f"Node pagination result may be incomplete for graph {graph_id}: "
                f"fetched {len(all_nodes)}, but count query reports {total}"
            )
    return result


def fetch_all_nodes(
    driver: GraphDriver,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> PagedResult:
    """分页获取图谱节点，最多返回 max_items 条（默认 2000）。每页请求自带重试。

    回傳值是 PagedResult（list 的子類別），正常當 list 用即可；如果需要感知
    FalkorDB 已知的游標分頁缺陷是否導致這次結果不完整，可以檢查
    `.is_complete`（見 PagedResult 說明）。
    """
    return asyncio.run(
        _fetch_all_nodes_async(driver, graph_id, page_size, max_items, max_retries, retry_delay)
    )


async def _fetch_all_edges_async(
    driver: GraphDriver,
    graph_id: str,
    page_size: int,
    max_retries: int,
    retry_delay: float,
) -> PagedResult:
    all_edges: list[EntityEdge] = []
    seen_uuids: set[str] = set()
    cursor: str | None = None
    page_num = 0

    while True:
        page_num += 1
        try:
            batch = await _fetch_page_with_retry(
                EntityEdge.get_by_group_ids,
                driver,
                [graph_id],
                limit=page_size,
                uuid_cursor=cursor,
                max_retries=max_retries,
                retry_delay=retry_delay,
                page_description=f"fetch edges page {page_num} (graph={graph_id})",
            )
        except GroupsEdgesNotFoundError:
            # 图谱没有任何边（例如刚建好但还没抽出关系）；沿用原 Zep 版本
            # "无边=空列表" 的语义，不当成错误。
            break

        if not batch:
            break

        # 去重防禦：同 _fetch_all_nodes_async——Stage 5 端到端測試用超過一頁
        # 的真實資料量（230 條邊、page_size=100 生產預設值）驗證過，FalkorDB
        # 的 `WHERE e.uuid < $uuid` 索引掃描缺陷不只會讓分頁卡在同一筆
        # （page_size=1 時最明顯），也會讓跨頁邊界重複吐出已經收過的邊，
        # 造成 fetch_all_edges 回傳的筆數「多於」實際總數。用 seen_uuids
        # 過濾每一頁，只保留真正沒看過的記錄，才能同時防住「卡住不前進」
        # 與「跨頁重複」這兩種表現。
        new_items = [e for e in batch if e.uuid not in seen_uuids]
        if not new_items:
            logger.warning(
                f"Edge pagination stuck (page {page_num} returned only already-seen records), "
                f"stopping at {len(all_edges)} edges for graph {graph_id} to avoid infinite loop"
            )
            break

        for e in new_items:
            seen_uuids.add(e.uuid)
        all_edges.extend(new_items)

        if len(batch) < page_size:
            break

        next_cursor = batch[-1].uuid
        if next_cursor is None:
            logger.warning(f"Edge missing uuid field, stopping pagination at {len(all_edges)} edges")
            break
        cursor = next_cursor

    result = PagedResult(all_edges)
    total = await _count_edges(driver, graph_id)
    if total is not None and total != len(all_edges):
        result.is_complete = False
        logger.warning(
            f"Edge pagination result may be incomplete for graph {graph_id}: "
            f"fetched {len(all_edges)}, but count query reports {total}"
        )
    return result


def fetch_all_edges(
    driver: GraphDriver,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> PagedResult:
    """分页获取图谱所有边，返回完整列表。每页请求自带重试。

    回傳值是 PagedResult（list 的子類別），正常當 list 用即可；如果需要感知
    FalkorDB 已知的游標分頁缺陷是否導致這次結果不完整，可以檢查
    `.is_complete`（見 PagedResult 說明）。
    """
    return asyncio.run(
        _fetch_all_edges_async(driver, graph_id, page_size, max_retries, retry_delay)
    )


def fetch_nodes_and_edges(
    driver: GraphDriver,
    graph_id: str,
    node_page_size: int = _DEFAULT_PAGE_SIZE,
    edge_page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    close_driver: bool = False,
) -> tuple[PagedResult, PagedResult]:
    """在同一個 event loop 內依序取得 nodes 與 edges。

    close_driver=True：查完後在同一個 loop 裡關閉 driver 的連線池。呼叫端若是
    「每次請求現建一個 driver、用完即丟」（例如 /api/graph/data 每 10 秒被前端
    輪詢一次），一定要開這個參數，否則每次輪詢都會遺留一組 FalkorDB 連線
    （實測一個建圖過程累積了 51 條沒關閉的連線）。連線綁在 event loop 上，
    必須在 asyncio.run() 結束前關，所以由這裡負責、不能交給呼叫端事後關。

    Stage 5 端到端測試對著真實 FalkorDB 實測發現：FalkorDB 的 async redis
    連線會綁定在建立當下的 event loop 上；如果分別呼叫 fetch_all_nodes() 和
    fetch_all_edges()（各自用自己的 asyncio.run() 開一個新 loop），同一個
    driver 物件底下快取的連線在第二次呼叫時會綁在已經關閉的第一個 loop 上，
    導致 `RuntimeError: Event loop is closed`。任何需要對同一個 driver 連續
    做多次查詢的呼叫端，都應該用這個函式而不是分開呼叫 fetch_all_nodes +
    fetch_all_edges。
    """
    async def _both() -> tuple[list[EntityNode], list[EntityEdge]]:
        try:
            nodes = await _fetch_all_nodes_async(
                driver, graph_id, node_page_size, max_items, max_retries, retry_delay
            )
            edges = await _fetch_all_edges_async(
                driver, graph_id, edge_page_size, max_retries, retry_delay
            )
            return nodes, edges
        finally:
            if close_driver:
                try:
                    await driver.close()
                except Exception as exc:  # 關閉失敗不影響已取得的資料
                    logger.debug(f"closing graph driver failed (ignored): {exc}")

    return asyncio.run(_both())
