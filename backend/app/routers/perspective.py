"""多视角查询 API"""

from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.models import (
    LeaderViewData, EngineerViewData, DataSourceInfo,
    BusinessDomain, DataMapping, FieldMapping
)

router = APIRouter(prefix="/api/perspective")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = BASE_DIR / "projects"


def _load_project(project_id: str) -> dict:
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise HTTPException(404, f"项目不存在: {project_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_source_type(origin: str) -> str:
    origin = (origin or "").strip()
    if ":" in origin:
        origin = origin.split(":", 1)[0].strip()
    if not origin:
        return "manual"
    if origin in {"excel", "csv", "dameng", "manual"}:
        return origin
    if origin == "sim_dameng":
        return "dameng"
    # 兼容旧版本：文件导入时曾把 file_id(uuid) 直接写入 origin
    if len(origin) == 36 and origin.count("-") == 4:
        return "excel"
    return "manual"


def _source_name_for_type(source_type: str) -> str:
    if source_type == "excel":
        return "导入的Excel数据源"
    if source_type == "csv":
        return "导入的CSV数据源"
    if source_type == "dameng":
        return "达梦数据库"
    return "系统默认数据源"


def _parse_origin(origin: str) -> tuple[str, str]:
    raw = (origin or "").strip()
    source_type = _normalize_source_type(raw)
    if ":" in raw:
        _, explicit_name = raw.split(":", 1)
        explicit_name = explicit_name.strip()
        if explicit_name:
            return source_type, explicit_name
    return source_type, _source_name_for_type(source_type)


def _source_table_label(source_type: str, source_name: str) -> str:
    if source_type in {"excel", "csv"}:
        return source_name
    if source_type == "manual":
        return "人工维护"
    return "默认映射表"


def _origin_to_source(origin: str) -> tuple[str, str, str]:
    source_type, source_name = _parse_origin(origin)
    if source_type == "manual":
        source_name = "人工维护数据"
    table_label = _source_table_label(source_type, source_name)
    return source_type, source_name, table_label


def _build_sources_from_nodes(nodes: list[dict], domain_id: str) -> list[dict]:
    groups: dict[tuple[str, str, str], dict] = {}
    for n in nodes:
        source_type, source_name, table_label = _origin_to_source(n.get("origin", "manual"))
        key = (source_type, source_name, table_label)
        if key not in groups:
            groups[key] = {
                "id": f"src-{source_type}-{len(groups) + 1}",
                "name": source_name,
                "type": source_type,
                "conn_info": {},
                "tables": [table_label],
                "covered_nodes": 0,
                "covered_domains": [domain_id],
                "total_fields": 0,
            }
        groups[key]["covered_nodes"] += 1
        groups[key]["total_fields"] += len(n.get("attributes", []) or [])
    return list(groups.values())


def _ensure_nodes_in_domains(domains: list[dict], nodes: list[dict]) -> list[dict]:
    if not domains:
        return domains

    node_ids = [n["id"] for n in nodes if n.get("id")]
    assigned = set()
    for d in domains:
        for nid in d.get("ontology_node_ids", []) or []:
            assigned.add(nid)

    missing = [nid for nid in node_ids if nid not in assigned]
    if not missing:
        return domains

    target = None
    for d in domains:
        if d.get("id") == "domain-default":
            target = d
            break
    if target is None:
        target = domains[0]

    target.setdefault("ontology_node_ids", [])
    for nid in missing:
        target["ontology_node_ids"].append(nid)
    return domains


def _build_default_perspective_config(project_id: str, graph: dict) -> dict:
    nodes = graph.get("nodes", [])
    if not nodes:
        return {"project_name": project_id, "domains": [], "mappings": [], "sources": []}

    domain_id = "domain-default"

    domains = [{
        "id": domain_id,
        "name": "默认业务域",
        "ontology_node_ids": [n["id"] for n in nodes],
        "databases": []
    }]

    sources = _build_sources_from_nodes(nodes, domain_id)
    domains[0]["databases"] = [s["name"] for s in sources]

    mappings = []
    for n in nodes:
        source_type, source_name, table_label = _origin_to_source(n.get("origin", "manual"))
        field_mappings = []
        for attr in n.get("attributes", []):
            field_mappings.append({
                "field_name": attr.get("key", ""),
                "attribute_key": attr.get("key", ""),
                "data_type": "VARCHAR"
            })
        mappings.append({
            "ontology_node_id": n["id"],
            "source_type": source_type,
            "source_name": source_name,
            "table_name": table_label,
            "field_mappings": field_mappings,
            "node_name": n.get("name", ""),
            "domain_id": domain_id
        })

    return {
        "project_name": project_id,
        "domains": domains,
        "sources": sources,
        "mappings": mappings
    }


def _normalize_perspective_config(project_id: str, graph: dict, config: dict) -> dict:
    normalized = dict(config)
    normalized.setdefault("project_name", project_id)
    normalized.setdefault("domains", [])
    normalized.setdefault("sources", [])
    normalized.setdefault("mappings", [])

    if not normalized["sources"] and not normalized["mappings"]:
        return _build_default_perspective_config(project_id, graph)

    nodes = graph.get("nodes", [])
    if not nodes:
        return normalized

    domains = [dict(d) for d in normalized.get("domains", [])]
    mappings = [dict(m) for m in normalized.get("mappings", [])]

    # 以图数据的 origin 为准：逐节点校正 mapping 的来源信息，并补全缺失节点的 mapping
    derived_by_node: dict[str, dict] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        source_type, source_name, table_label = _origin_to_source(n.get("origin", "manual"))
        field_mappings = []
        for attr in n.get("attributes", []):
            field_mappings.append({
                "field_name": attr.get("key", ""),
                "attribute_key": attr.get("key", ""),
                "data_type": "VARCHAR"
            })
        derived_by_node[nid] = {
            "ontology_node_id": nid,
            "source_type": source_type,
            "source_name": source_name,
            "table_name": table_label,
            "field_mappings": field_mappings,
            "node_name": n.get("name", ""),
        }

    mapping_map = {m.get("ontology_node_id"): m for m in mappings if m.get("ontology_node_id")}
    for nid, derived in derived_by_node.items():
        existing = mapping_map.get(nid)
        if existing is None:
            mappings.append({
                **derived,
                "domain_id": "",
            })
            continue
        existing["source_type"] = derived["source_type"]
        existing["source_name"] = derived["source_name"]
        existing["table_name"] = derived["table_name"]

    # sources 统一从图数据重建，确保 Excel + 人工维护能同时出现
    sources = _build_sources_from_nodes(nodes, "domain-default")

    # domains：确保新增节点归属某个域
    if not domains:
        domains = [{
            "id": "domain-default",
            "name": "默认业务域",
            "ontology_node_ids": [n["id"] for n in nodes if n.get("id")],
            "databases": [s["name"] for s in sources],
        }]
    else:
        domains = _ensure_nodes_in_domains(domains, nodes)
        if domains and not (domains[0].get("databases") or []):
            domains[0]["databases"] = [s["name"] for s in sources]

    normalized["domains"] = domains
    normalized["sources"] = sources
    normalized["mappings"] = mappings
    return normalized


def _load_perspective_config(project_id: str) -> dict:
    graph = _load_project(project_id)
    config_path = PROJECTS_DIR / f"{project_id}_perspective.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return _normalize_perspective_config(project_id, graph, config)
    return _build_default_perspective_config(project_id, graph)


def _save_perspective_config(project_id: str, config: dict):
    config_path = PROJECTS_DIR / f"{project_id}_perspective.json"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ============================================================
# 视角数据获取
# ============================================================

@router.get("/{project_id}/leader")
async def get_leader_view(project_id: str):
    """返回领导视角完整数据"""
    graph = _load_project(project_id)
    config = _load_perspective_config(project_id)

    domains = [BusinessDomain(**d) for d in config.get("domains", [])]
    sources = [DataSourceInfo(**s) for s in config.get("sources", [])]

    node_map = {n["id"]: n.get("name", n["id"]) for n in graph.get("nodes", [])}
    mappings = config.get("mappings", [])
    source_onto_map: dict[str, list[str]] = {}
    for m in mappings:
        sn = m.get("source_name", "")
        nid = m.get("ontology_node_id", "")
        name = node_map.get(nid, nid)
        if sn not in source_onto_map:
            source_onto_map[sn] = []
        if name not in source_onto_map[sn]:
            source_onto_map[sn].append(name)
    for src in sources:
        src.covered_ontology_names = source_onto_map.get(src.name, [])

    source_domain_map = {}
    for src in sources:
        source_domain_map[src.id] = [
            d.id for d in domains
            if src.id in d.databases or src.name in d.databases
        ]

    manual_node_ids = [n["id"] for n in graph.get("nodes", []) if n.get("origin", "manual") == "manual"]
    manual_node_names = [n.get("name", n["id"]) for n in graph.get("nodes", []) if n.get("origin", "manual") == "manual"]
    manual_edge_count = sum(1 for e in graph.get("edges", []) if e.get("origin", "manual") == "manual")

    return LeaderViewData(
        summary={
            "domain_count": len(domains),
            "node_count": len(graph.get("nodes", [])),
            "inference_count": len(graph.get("edges", [])),
            "source_count": len(sources),
            "source_distribution": {
                "dameng": sum(1 for s in sources if s.type == "dameng"),
                "excel": sum(1 for s in sources if s.type == "excel"),
                "csv": sum(1 for s in sources if s.type == "csv"),
            },
            "manual_node_count": len(manual_node_ids),
            "manual_edge_count": manual_edge_count,
            "manual_node_names": manual_node_names,
        },
        data_sources=sources,
        domains=domains,
        source_domain_map=source_domain_map
    )


@router.get("/{project_id}/engineer")
async def get_engineer_view(project_id: str):
    """返回软件工程师视角完整数据"""
    graph = _load_project(project_id)
    config = _load_perspective_config(project_id)

    project_name = config.get("project_name", project_id)
    domains = [BusinessDomain(**d) for d in config.get("domains", [])]
    raw_mappings = config.get("mappings", [])

    node_map = {n["id"]: n for n in graph.get("nodes", [])}

    # 构建 ontology_node_id → domain_id 映射
    node_domain_map = {}
    for d in domains:
        for nid in d.ontology_node_ids:
            node_domain_map[nid] = d.id

    # 丰富 mapping 数据，添加 node_name 和 domain_id
    enriched_mappings = []
    nodes_brief = []
    seen_nodes = set()
    for m in raw_mappings:
        nid = m.get("ontology_node_id", "")
        node = node_map.get(nid)
        if not node:
            continue
        node_name = node.get("name", nid)
        enriched = dict(m)
        enriched["node_name"] = node_name
        enriched["domain_id"] = node_domain_map.get(nid, "_other")
        enriched_mappings.append(DataMapping(**enriched))

        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes_brief.append({"id": nid, "name": node_name})

    return EngineerViewData(
        project_name=project_name,
        nodes=nodes_brief,
        mappings=enriched_mappings,
        domains=domains
    )


@router.get("/{project_id}/process")
async def get_process_view(project_id: str):
    """返回工艺人员视角数据 -- 即完整图数据"""
    return _load_project(project_id)


# ============================================================
# 配置管理
# ============================================================

@router.get("/{project_id}/domains")
async def get_domains(project_id: str):
    config = _load_perspective_config(project_id)
    return {"domains": config.get("domains", [])}


@router.put("/{project_id}/domains")
async def update_domains(project_id: str, domains: list[BusinessDomain]):
    config = _load_perspective_config(project_id)
    config["domains"] = [d.model_dump() for d in domains]
    _save_perspective_config(project_id, config)
    return {"success": True}


@router.put("/{project_id}/mappings")
async def update_mappings(project_id: str, mappings: list[DataMapping]):
    config = _load_perspective_config(project_id)
    config["mappings"] = [m.model_dump() for m in mappings]
    _save_perspective_config(project_id, config)
    return {"success": True}


@router.get("/{project_id}/sources")
async def get_sources(project_id: str):
    config = _load_perspective_config(project_id)
    return {"sources": config.get("sources", [])}


@router.put("/{project_id}/sources")
async def update_sources(project_id: str, sources: list[DataSourceInfo]):
    config = _load_perspective_config(project_id)
    config["sources"] = [s.model_dump() for s in sources]
    _save_perspective_config(project_id, config)
    return {"success": True}
