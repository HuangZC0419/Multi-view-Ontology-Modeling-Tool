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


def _load_perspective_config(project_id: str) -> dict:
    config_path = PROJECTS_DIR / f"{project_id}_perspective.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {"domains": [], "mappings": [], "sources": []}


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

    mapped_node_ids = set()
    for m in mappings:
        mapped_node_ids.add(m.get("ontology_node_id", ""))
    manual_node_ids = [n["id"] for n in graph.get("nodes", []) if n["id"] not in mapped_node_ids]
    manual_node_names = [node_map[nid] for nid in manual_node_ids if nid in node_map]

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
            "manual_edge_count": len(graph.get("edges", [])),
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
