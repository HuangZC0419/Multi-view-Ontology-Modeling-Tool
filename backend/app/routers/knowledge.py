"""知识检索 API -- 单个项目内跨概念名称、概念属性、关系名称与数据来源的跨维度检索"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# 合法的检索范围
_VALID_SCOPES = {"concept", "attribute", "relation", "source"}


class ConceptMatch(BaseModel):
    """命中的知识概念"""

    id: str
    name: str
    match_field: str  # 取值域：name | attribute | source
    match_snippet: str  # 命中字段的完整原值，非上下文片段
    parent_path: str = ""
    origin: str = "manual"
    attributes: list[dict[str, str]] = Field(default_factory=list)


class RelationMatch(BaseModel):
    """命中的知识关系"""

    id: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relation: str
    match_field: str  # relation | source
    origin: str = "manual"


class KnowledgeSearchResponse(BaseModel):
    query: str
    total: int  # 本次实际返回的条数（受 limit 截断），而非命中总数
    concepts: list[ConceptMatch] = Field(default_factory=list)
    relations: list[RelationMatch] = Field(default_factory=list)


def _parse_scopes(raw: str) -> set[str]:
    """将 'concept,attribute' 解析为范围集合；非法或空值回退为 all"""
    parts = {p.strip().lower() for p in (raw or "").split(",") if p.strip()}
    if not parts or "all" in parts:
        return {"all"}
    valid = parts & _VALID_SCOPES
    return valid or {"all"}


def _in(scope: str, scopes: set[str]) -> bool:
    return "all" in scopes or scope in scopes


def _build_parent_path(node: Any, node_map: dict[str, Any]) -> str:
    """沿 parent_id 向上回溯，返回 'A / B / ' 形式的祖先路径（自动防环）"""
    parts: list[str] = []
    seen: set[str] = set()
    current = node
    while current is not None and current.parent_id:
        pid = current.parent_id
        if pid in seen:
            break
        seen.add(pid)
        parent = node_map.get(pid)
        if parent is None:
            break
        parts.append(parent.name)
        current = parent
    if not parts:
        return ""
    return " / ".join(reversed(parts)) + " / "


def _match_node(node: Any, kw: str, scopes: set[str]) -> tuple[str, str] | None:
    """返回 (match_field, match_snippet)；未命中返回 None"""
    if _in("concept", scopes) and kw in (node.name or "").lower():
        return ("name", node.name)

    if _in("attribute", scopes):
        for attr in node.attributes or []:
            key = str(attr.get("key", ""))
            value = str(attr.get("value", ""))
            if kw in key.lower() or kw in value.lower():
                return ("attribute", f"{key}: {value}")

    if _in("source", scopes) and kw in (node.origin or "").lower():
        return ("source", node.origin)

    return None


def _match_edge(edge: Any, kw: str, scopes: set[str]) -> tuple[str, str] | None:
    """返回 (match_field, match_snippet)；未命中返回 None"""
    if _in("relation", scopes) and kw in (edge.relation or "").lower():
        return ("relation", edge.relation)

    if _in("source", scopes) and kw in (edge.origin or "").lower():
        return ("source", edge.origin)

    return None


@router.get("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    project_id: str = Query(..., description="项目 ID"),
    q: str = Query(..., min_length=1, description="检索关键词"),
    scope: str = Query("all", description="检索范围，逗号分隔：concept,attribute,relation,source"),
    limit: int = Query(50, ge=1, le=200, description="概念与关系各自的返回上限"),
) -> KnowledgeSearchResponse:
    """在指定项目的知识图谱中，跨概念名称、属性、关系与数据来源进行检索。

    匹配规则：大小写不敏感的包含匹配。项目不存在时返回空结果集。
    """
    # 延迟导入：main 模块在导入期会注册本路由，模块级导入会形成循环依赖
    from app.main import _load_project_data

    graph = _load_project_data(project_id)
    kw = q.strip().lower()
    if not kw:
        # 全空白查询：strip 后为空串，而 "" in s 恒为真，会误命中全部数据
        return KnowledgeSearchResponse(query=q, total=0)
    scopes = _parse_scopes(scope)

    node_map = {n.id: n for n in graph.nodes}

    concepts: list[ConceptMatch] = []
    for node in graph.nodes:
        hit = _match_node(node, kw, scopes)
        if hit is None:
            continue
        concepts.append(
            ConceptMatch(
                id=node.id,
                name=node.name,
                match_field=hit[0],
                match_snippet=hit[1],
                parent_path=_build_parent_path(node, node_map),
                origin=node.origin or "manual",
                attributes=node.attributes or [],
            )
        )
        if len(concepts) >= limit:
            break

    relations: list[RelationMatch] = []
    for edge in graph.edges:
        hit = _match_edge(edge, kw, scopes)
        if hit is None:
            continue
        source = node_map.get(edge.source)
        target = node_map.get(edge.target)
        relations.append(
            RelationMatch(
                id=edge.id,
                source_id=edge.source,
                source_name=source.name if source else edge.source,
                target_id=edge.target,
                target_name=target.name if target else edge.target,
                relation=edge.relation,
                match_field=hit[0],
                origin=edge.origin or "manual",
            )
        )
        if len(relations) >= limit:
            break

    return KnowledgeSearchResponse(
        query=q,
        total=len(concepts) + len(relations),
        concepts=concepts,
        relations=relations,
    )
