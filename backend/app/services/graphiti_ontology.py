"""
本體轉換工具：把既有（原本餵給 Zep SDK 的）本體定義字典，轉換成 Graphiti
add_episode() 所需的 entity_types / edge_types / edge_type_map 三件套。

既有 ontology dict 形狀（見 graph_builder.py 舊版 set_ontology() 的輸入）：
{
  "entity_types": [
    {"name": str, "description": str,
     "attributes": [{"name": str, "description": str}, ...]},
    ...
  ],
  "edge_types": [
    {"name": str, "description": str, "attributes": [...],
     "source_targets": [{"source": str, "target": str}, ...]},
    ...
  ]
}

Graphiti 要的目標形狀：
  entity_types:  dict[str, type[BaseModel]]        型別名 -> pydantic 動態模型
  edge_types:    dict[str, type[BaseModel]]         邊型別名 -> pydantic 動態模型
  edge_type_map: dict[tuple[str, str], list[str]]   (來源型別, 目標型別) -> 允許出現的邊型別名清單

這是 Zep 與 Graphiti 之間唯一實質不同的地方：Zep 把 source/target 掛在每個邊
型別底下（source_targets 清單），Graphiti 反過來把 (source, target) 當 key，
值是允許在這個方向上出現的邊型別名清單——同一組 (source, target) 可以對應多種
邊型別，同一種邊型別也可以出現在多組 (source, target) 底下。本函式把 Zep 形狀
「展開再反轉」成 Graphiti 形狀。未指定 source_targets 的邊型別維持 Zep 版本的
既有行為（不建立方向限制，不進 edge_type_map，只登記在 edge_types）。
"""

from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, Field

# Graphiti 保留欄位名：與 EntityNode / EntityEdge 既有欄位撞名會在
# graphiti_core.utils.ontology_utils.entity_types_utils.validate_entity_types()
# 被擋下（拋出 EntityTypeValidationError），因此在建模型前就要重新命名，行為與
# Zep 版本 graph_builder.py 的 safe_attr_name 一致。
ENTITY_RESERVED_NAMES = frozenset({
    "uuid", "name", "group_id", "labels", "created_at", "name_embedding",
    "summary", "attributes",
})
EDGE_RESERVED_NAMES = frozenset({
    "uuid", "group_id", "source_node_uuid", "target_node_uuid", "created_at",
    "name", "fact", "fact_embedding", "episodes", "expired_at", "valid_at",
    "invalid_at", "reference_time", "attributes",
})

# Graphiti 的通用實體標籤；edge_type_map 找不到對應的 (source, target) 組合時，
# graphiti_core 內部會 fallback 成 ('Entity', 'Entity')（見 edge_operations.py）。
DEFAULT_ENTITY_LABEL = "Entity"


def _safe_attr_name(attr_name: str, reserved: frozenset) -> str:
    """保留名稱轉換為安全名稱，避免撞到 Graphiti 節點/邊的既有欄位。"""
    if attr_name.lower() in reserved:
        return f"attr_{attr_name}"
    return attr_name


def _build_dynamic_model(
    name: str,
    description: str,
    attribute_defs: List[Dict[str, Any]],
    reserved: frozenset,
) -> Type[BaseModel]:
    attrs: Dict[str, Any] = {"__doc__": description}
    annotations: Dict[str, Any] = {}

    for attr_def in attribute_defs:
        attr_name = _safe_attr_name(attr_def["name"], reserved)
        attr_desc = attr_def.get("description", attr_name)
        attrs[attr_name] = Field(description=attr_desc, default=None)
        annotations[attr_name] = Optional[str]

    attrs["__annotations__"] = annotations
    model = type(name, (BaseModel,), attrs)
    model.__doc__ = description
    return model


def convert_ontology(
    ontology: Dict[str, Any],
) -> Tuple[Dict[str, Type[BaseModel]], Dict[str, Type[BaseModel]], Dict[Tuple[str, str], List[str]]]:
    """把既有 ontology dict 轉成 Graphiti add_episode() 需要的三件套。

    Returns:
        (entity_types, edge_types, edge_type_map)
    """
    entity_types: Dict[str, Type[BaseModel]] = {}
    for entity_def in ontology.get("entity_types") or []:
        name = entity_def["name"]
        description = entity_def.get("description", f"A {name} entity.")
        entity_types[name] = _build_dynamic_model(
            name, description, entity_def.get("attributes") or [], ENTITY_RESERVED_NAMES
        )

    edge_types: Dict[str, Type[BaseModel]] = {}
    edge_type_map: Dict[Tuple[str, str], List[str]] = {}

    for edge_def in ontology.get("edge_types") or []:
        name = edge_def["name"]
        description = edge_def.get("description", f"A {name} relationship.")
        edge_types[name] = _build_dynamic_model(
            name, description, edge_def.get("attributes") or [], EDGE_RESERVED_NAMES
        )

        source_targets = edge_def.get("source_targets") or []
        for st in source_targets:
            source = st.get("source") or DEFAULT_ENTITY_LABEL
            target = st.get("target") or DEFAULT_ENTITY_LABEL
            key = (source, target)
            names_for_key = edge_type_map.setdefault(key, [])
            if name not in names_for_key:
                names_for_key.append(name)

    return entity_types, edge_types, edge_type_map
