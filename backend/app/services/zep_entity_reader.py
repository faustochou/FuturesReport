"""
图谱实体读取与过滤服务
从 Graphiti/FalkorDB 图谱中读取节点，筛选出符合预定义实体类型的节点

模块名/类名沿用 zep_entity_reader / ZepEntityReader，让既有调用方（api/simulation.py、
oasis_profile_generator.py 等）保持最小改动——只需要把建构子的 api_key 换成
user_llm_config，其余方法签名不变。
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from .graphiti_factory import build_graphiti
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('futuresreport.zep_entity_reader')


@dataclass
class EntityNode:
    """实体节点数据结构"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """获取实体类型（排除默认的Entity标签）"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """过滤后的实体集合"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    图谱实体读取与过滤服务（Graphiti/FalkorDB 实现）

    主要功能：
    1. 从图谱读取所有节点（按 group_id=graph_id 分区）
    2. 筛选出符合预定义实体类型的节点（Labels不只是Entity的节点）
    3. 获取每个实体的相关边和关联节点信息

    纯读取操作（Cypher MATCH，不涉及向量搜索），不需要做 embedding 一致性检查——
    只有 search_graph 这类真正的语义搜索才需要（见 zep_tools.py）。
    """

    def __init__(self, user_llm_config: Dict[str, str]):
        if not user_llm_config or not user_llm_config.get("api_key"):
            raise ValueError("LLM 设定缺失：请先配置 BYOK LLM 供应商与 API Key")
        self.user_llm_config = user_llm_config

    def _driver(self, graph_id: str):
        # graph_id 必须传入：FalkorDB 的多租戶隔離是「每個 group_id 對應一個
        # 獨立命名的 FalkorDB 資料庫」（graphiti-core 的 add_episode() 內部會
        # clone driver 成 database=group_id），build_graphiti() 沒收到
        # graph_id 就會退回預設的 'default_db'，查不到實際寫入的資料
        # （Stage 5 端到端測試對真實 FalkorDB 實測到的問題）。
        return build_graphiti(self.user_llm_config, graph_id).driver

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """获取图谱的所有节点（分页获取）"""
        logger.info(f"获取图谱 {graph_id} 的所有节点...")

        nodes = fetch_all_nodes(self._driver(graph_id), graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": node.uuid,
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"共获取 {len(nodes_data)} 个节点")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """获取图谱的所有边（分页获取）"""
        logger.info(f"获取图谱 {graph_id} 的所有边...")

        edges = fetch_all_edges(self._driver(graph_id), graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": edge.uuid,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"共获取 {len(edges_data)} 条边")
        return edges_data

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[Dict[str, Any]]:
        """获取指定节点的所有相关边（通过获取图谱所有边后过滤，与 zep_tools.py 的
        同名方法策略一致——Graphiti 没有"取单节点的边"这种按需查询 API，
        全量取回再过滤在图谱规模较小时是可接受的）。"""
        try:
            all_edges = self.get_all_edges(graph_id)
            return [
                e for e in all_edges
                if e["source_node_uuid"] == node_uuid or e["target_node_uuid"] == node_uuid
            ]
        except Exception as e:
            logger.warning(f"获取节点 {node_uuid} 的边失败: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """筛选出符合预定义实体类型的节点"""
        logger.info(f"开始筛选图谱 {graph_id} 的实体...")

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []

        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities = []
        entity_types_found = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })

                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"筛选完成: 总节点 {total_count}, 符合条件 {len(filtered_entities)}, "
                   f"实体类型: {entity_types_found}")

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """获取单个实体及其完整上下文（边和关联节点）"""
        try:
            from graphiti_core.nodes import EntityNode as GraphitiEntityNode

            import asyncio
            node = asyncio.run(GraphitiEntityNode.get_by_uuid(self._driver(graph_id), entity_uuid))

            if not node:
                return None

            edges = self.get_node_edges(graph_id, entity_uuid)

            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            related_edges = []
            related_node_uuids = set()

            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })

            return EntityNode(
                uuid=node.uuid,
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"获取实体 {entity_uuid} 失败: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """获取指定类型的所有实体"""
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
