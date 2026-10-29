"""
图谱构建服务
接口2：使用 Graphiti + FalkorDB 构建 Standalone Graph（BYOK：LLM/embedding 用使用者自己的模型）
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from falkordb.asyncio import FalkorDB
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.bulk_utils import RawEpisode
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from ..models.task import TaskManager, TaskStatus
from ..utils.zep_paging import fetch_nodes_and_edges
from ..utils.locale import t, get_locale, set_locale
from ..utils.logger import get_logger
from .text_processor import TextProcessor
from .graphiti_factory import (
    build_graphiti,
    precheck_llm,
    enforce_embedding_consistency,
    get_embedding_identity,
    redact_secrets,
    UnsupportedProviderError,
    EmbeddingMismatchError,
    DEFAULT_FALKORDB_HOST,
    DEFAULT_FALKORDB_PORT,
    FALKORDB_SOCKET_CONNECT_TIMEOUT,
    FALKORDB_SOCKET_TIMEOUT,
)
from .graphiti_ontology import convert_ontology

logger = get_logger('futuresreport.graph_builder')

# 每次 add_episode_bulk() 一起送進 Graphiti 的 chunk 數。一批之內所有 LLM 呼叫
# 並行（受 GRAPHITI_MAX_COROUTINES 限制），批與批之間依序執行；總時間大致是
# 「批數 × 每批約 6–7 輪 LLM 往返」，所以批次越大越快。批內的實體去重由
# graphiti_batch.BatchDedupGraphiti 補上 LLM 比對，品質與小批次相同。
GRAPH_BULK_BATCH_SIZE = max(1, int(os.environ.get("GRAPH_BULK_BATCH_SIZE", "100")))
# 單一批次的最長處理時間（秒）。LLM 請求本身已有逾時（graphiti_factory），這是
# 最後一道保險：任何未預期的卡住都會在這個時間後變成明確的失敗，而不是讓建圖
# 任務永遠停在某個百分比。
GRAPH_BULK_BATCH_TIMEOUT = int(os.environ.get("GRAPH_BULK_BATCH_TIMEOUT", "1800"))

# 原本這裡有一個進程級旗標 `_indices_built`，假設「FalkorDB 的索引是 label 級的，
# 跨所有 group_id 共用」，只在進程生命週期內成功建過一次索引就永遠跳過。這個假設
# 是錯的：Stage 5 對真實 FalkorDB 實測直接驗證過——對從沒呼叫過
# build_indices_and_constraints() 的圖譜跑 `CALL DB.INDEXES()` 回傳 0 筆，對呼叫過的
# 圖譜回傳 9 筆，證明索引是逐資料庫（逐 graph_id）的，不是全域共用。用單一布林旗標
# 的後果：同一個後端行程裡，第一個成功建圖的 graph_id 之後，其餘所有 graph_id
# 永遠不會真的建立索引（不會報錯，只是靜默退化成無索引全掃描，效能下降，且不易
# 察覺）。
#
# 修法：拿掉快取旗標，改成每次建圖都直接呼叫 build_indices_and_constraints()——
# 同樣用 Stage 5 對真實 FalkorDB 實測驗證過這是冪等操作：對同一個 database 連續
# 呼叫兩次、甚至換一個全新的 driver 實例再呼叫第三次，均未拋出例外（背後原因是
# graphiti-core 的 FalkorDriver.execute_query() 自己會攔截 'already indexed' 字樣的
# 例外訊息、當成無害情況吞掉並回傳 None，不會往外拋）。既然已確認冪等且成本低
# （索引已存在時，每個查詢就是一次快速的「已存在」回應），比起維護一個容易踩錯的
# 快取旗標，直接每次都呼叫更簡單、也更正確——下方 try/except 保留下來只是防禦
# 真正的連線類例外（非「已存在」情況），不是為了掩蓋索引重複建立的錯誤。


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    图谱构建服务
    负责用使用者的 BYOK LLM 设定组装 Graphiti，对 FalkorDB 构建知识图谱

    与旧版 Zep 实现的关键差异：
    - 没有「等待 episode 处理完成」的概念——add_episode() 是同步完成抽取的
      （每次调用内部就跑完 LLM 抽取 + 写图），不像 Zep 那样是先排队、后台异步处理、
      需要轮询 processed 状态。所以这里没有 _wait_for_episodes()。
    - 每个 chunk 各自一次 add_episode() 调用，进度回调直接对应每个 chunk 完成，
      不再有「发送完成」与「处理完成」两段式进度。
    """

    def __init__(self, user_llm_config: Dict[str, str]):
        if not user_llm_config or not user_llm_config.get("api_key"):
            raise ValueError(t('api.llmConfigMissing'))
        self.user_llm_config = user_llm_config
        self.task_manager = TaskManager()

    def precheck(self) -> tuple:
        """建圖前的 LLM 可用性預檢（結構化輸出 + embedding）。回傳 (ok, reason)。"""
        return asyncio.run(precheck_llm(self.user_llm_config))

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "Futures Report Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """异步构建图谱"""
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        current_locale = get_locale()

        import threading
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh'
    ):
        """图谱构建工作线程"""
        set_locale(locale)
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph')
            )

            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=t('progress.graphCreated', graphId=graph_id)
            )

            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message=t('progress.ontologySet')
            )

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=t('progress.textSplit', count=total_chunks)
            )

            self.add_text_batches(
                graph_id, chunks, ontology, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.7),  # 20-90%
                    message=msg
                )
            )

            self.task_manager.update_task(
                task_id,
                progress=90,
                message=t('progress.fetchingGraphInfo')
            )

            graph_info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{redact_secrets(str(e))}\n{redact_secrets(traceback.format_exc())}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """创建图谱 ID（公开方法）。FalkorDB 本身不需要预先"创建"一个图谱容器——
        group_id 是首次 add_episode 时才实际产生数据的逻辑分区，这里只是生成 ID。"""
        return f"fr_{uuid.uuid4().hex[:16]}"

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        """转换并缓存本体（公开方法，与旧版签名一致）。

        Graphiti 没有「预先注册本体」的概念——entity_types/edge_types/edge_type_map
        是每次 add_episode() 调用时传入的参数，不是像 Zep 那样先用一个 API 调用
        设置到服务端。这里把转换结果缓存在实例上，供 add_text_batches 使用。
        """
        entity_types, edge_types, edge_type_map = convert_ontology(ontology)
        self._entity_types = entity_types
        self._edge_types = edge_types
        self._edge_type_map = edge_type_map

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        ontology: Optional[Dict[str, Any]] = None,
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """以 Graphiti add_episode_bulk() 分批写入所有 chunk，返回 episode uuid 列表。

        每批 GRAPH_BULK_BATCH_SIZE 个 chunk：批内并行抽取（逐块 add_episode()
        是完全序列化的，一份长文件要跑好几个小时），批与批之间依序执行，
        后一批的去重能看到前一批写入的实体。每批完成后回报一次进度。

        batch_size 参数保留是为了不打破既有调用签名，实际批次大小由
        GRAPH_BULK_BATCH_SIZE 决定。
        """
        if ontology is not None and not hasattr(self, '_entity_types'):
            self.set_ontology(graph_id, ontology)

        entity_types = getattr(self, '_entity_types', {})
        edge_types = getattr(self, '_edge_types', {})
        edge_type_map = getattr(self, '_edge_type_map', {})

        try:
            graphiti = build_graphiti(self.user_llm_config, graph_id)
        except UnsupportedProviderError:
            raise
        except (RedisConnectionError, RedisTimeoutError) as e:
            raise RuntimeError(t('api.falkordbConnectionError', detail=redact_secrets(str(e)))) from e

        episode_uuids = []
        total_chunks = len(chunks)

        async def _add_all():
            try:
                await graphiti.build_indices_and_constraints()
            except Exception as e:
                # 已确认冪等（见上方模块级注释），这里只防御真正的连线类例外；
                # 真正的连线问题也会在下面的 add_episode 调用中作为
                # RedisConnectionError 浮现并中断整个建图流程，这里不需要重复处理，
                # 记 debug 日志即可，不影响本次建图继续往下走。
                logger.debug(f"build_indices_and_constraints failed (non-fatal, continuing): {redact_secrets(str(e))}")

            try:
                for start in range(0, total_chunks, GRAPH_BULK_BATCH_SIZE):
                    batch = chunks[start:start + GRAPH_BULK_BATCH_SIZE]
                    batch_no = start // GRAPH_BULK_BATCH_SIZE + 1
                    reference_time = datetime.now(timezone.utc)
                    raw_episodes = [
                        RawEpisode(
                            name=f"{graph_id}_chunk_{start + offset}",
                            content=chunk,
                            source_description="Futures Report document chunk",
                            source=EpisodeType.text,
                            reference_time=reference_time,
                        )
                        for offset, chunk in enumerate(batch)
                    ]
                    try:
                        result = await asyncio.wait_for(
                            graphiti.add_episode_bulk(
                                raw_episodes,
                                group_id=graph_id,
                                entity_types=entity_types or None,
                                edge_types=edge_types or None,
                                edge_type_map=edge_type_map or None,
                            ),
                            timeout=GRAPH_BULK_BATCH_TIMEOUT,
                        )
                        episode_uuids.extend(ep.uuid for ep in result.episodes)
                    except (RedisConnectionError, RedisTimeoutError):
                        raise
                    except Exception as e:
                        detail = redact_secrets(str(e)) or e.__class__.__name__
                        if progress_callback:
                            progress_callback(
                                t('progress.batchFailed', batch=batch_no, error=detail), 0
                            )
                        raise RuntimeError(t('api.llmExtractionError', detail=detail)) from e

                    if progress_callback:
                        done = start + len(batch)
                        progress_callback(
                            t('progress.sendingBatch', current=done, total=total_chunks, chunks=len(batch)),
                            done / total_chunks
                        )
            finally:
                # 建圖用的 driver 只活在這次 asyncio.run() 裡，結束時一併關閉連線池。
                try:
                    await graphiti.driver.close()
                except Exception as exc:
                    logger.debug(f"closing graph driver failed (ignored): {exc}")

        try:
            asyncio.run(_add_all())
        except (RedisConnectionError, RedisTimeoutError) as e:
            raise RuntimeError(t('api.falkordbConnectionError', detail=redact_secrets(str(e)))) from e

        return episode_uuids

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱信息"""
        graphiti = build_graphiti(self.user_llm_config, graph_id)
        # 用 fetch_nodes_and_edges（单一 event loop 内完成两次查询），不要分开
        # 呼叫 fetch_all_nodes + fetch_all_edges——同一个 driver 的底层 async
        # redis 连线绑在建立时的 event loop 上，分开呼叫会在第二次触发
        # "Event loop is closed"（Stage 5 端到端测试对真实 FalkorDB 实测到的）。
        nodes, edges = fetch_nodes_and_edges(graphiti.driver, graph_id, close_driver=True)

        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据（包含详细信息），供 /data/<graph_id> 接口使用"""
        enforce_embedding_consistency(self.user_llm_config, graph_id)

        graphiti = build_graphiti(self.user_llm_config, graph_id)
        nodes, edges = fetch_nodes_and_edges(graphiti.driver, graph_id, close_driver=True)

        node_map = {}
        for node in nodes:
            node_map[node.uuid] = node.name or ""

        nodes_data = []
        for node in nodes:
            created_at = getattr(node, 'created_at', None)
            nodes_data.append({
                "uuid": node.uuid,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": str(created_at) if created_at else None,
            })

        edges_data = []
        for edge in edges:
            created_at = getattr(edge, 'created_at', None)
            valid_at = getattr(edge, 'valid_at', None)
            invalid_at = getattr(edge, 'invalid_at', None)
            expired_at = getattr(edge, 'expired_at', None)
            episodes = getattr(edge, 'episodes', None) or []

            edges_data.append({
                "uuid": edge.uuid,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": edge.name or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": [str(e) for e in episodes] if episodes else [],
            })

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def get_embedding_metadata(self) -> Dict[str, str]:
        """回傳這次建圖要寫入專案 metadata 的 embedding 供應商/模型（呼叫端在
        建圖成功後應該把這組值存到 Project.embedding_provider/embedding_model，
        供之後的一致性檢查使用；見 graphiti_factory.enforce_embedding_consistency）。
        """
        provider = (self.user_llm_config.get("provider") or "").strip().lower()
        return {
            "embedding_provider": provider,
            "embedding_model": get_embedding_identity(provider),
        }

    def delete_graph(self, graph_id: str):
        """删除图谱（实例方法，向后兼容既有调用方式）。委托给不需要 BYOK
        LLM 设定的模块级函数，见 delete_graph_by_id() 的说明。"""
        delete_graph_by_id(graph_id)


def delete_graph_by_id(graph_id: str) -> None:
    """删除图谱：清除 FalkorDB 中该图谱的所有节点/边/episode。

    刻意不透过 build_graphiti()（不组装 LLM/embedder）——删除是纯 FalkorDB
    结构性操作，不应该因为使用者的 LLM key 失效/额度用尽而被挡住：这会造成
    「想删除一个建图失败的项目，却因为同一个坏掉的 LLM key 而删不掉」的死锁。

    database=graph_id 是关键：FalkorDB 的多租戶隔離是「每個 group_id 對應
    一個獨立命名的 FalkorDB 資料庫」（graphiti-core 的 add_episode() 內部會
    clone driver 成 database=group_id，見 graphiti_factory.build_graphiti()
    的說明），不是同一張圖裡的篩選條件。少了這個參數，driver 會退回預設的
    'default_db'，這個函式會在一個空的資料庫上執行 DELETE、變成靜默的
    no-op——實際資料完全沒被刪掉（Stage 5 端到端測試對真實 FalkorDB 實測
    到的問題：先前所有測試跑完顯示「已刪除」，其實從未真正刪過任何東西）。
    這裡改用 group_id 本身當 database 名稱，就不再需要 WHERE group_id 篩選，
    直接清空這個 database 底下的所有節點即可。
    """
    falkor_client = FalkorDB(
        host=os.environ.get("FALKORDB_HOST", DEFAULT_FALKORDB_HOST),
        port=int(os.environ.get("FALKORDB_PORT", str(DEFAULT_FALKORDB_PORT))),
        password=os.environ.get("FALKORDB_PASSWORD") or None,
        socket_connect_timeout=FALKORDB_SOCKET_CONNECT_TIMEOUT,
        socket_timeout=FALKORDB_SOCKET_TIMEOUT,
    )
    driver = FalkorDriver(
        falkor_db=falkor_client,
        database=graph_id,
    )

    async def _clear():
        try:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
        finally:
            await driver.close()

    asyncio.run(_clear())
