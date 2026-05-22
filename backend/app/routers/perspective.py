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

    source_domain_map = {}
    for src in sources:
        source_domain_map[src.id] = [
            d.id for d in domains
            if src.id in d.databases or src.name in d.databases
        ]

    return LeaderViewData(
        summary={
            "domains": len(domains),
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "sources": len(sources),
            "dameng_count": sum(1 for s in sources if s.type == "dameng"),
            "excel_count": sum(1 for s in sources if s.type == "excel"),
            "csv_count": sum(1 for s in sources if s.type == "csv"),
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

    domains = [BusinessDomain(**d) for d in config.get("domains", [])]
    mappings = [DataMapping(**m) for m in config.get("mappings", [])]

    node_map = {n["id"]: n for n in graph.get("nodes", [])}
    nodes_brief = [
        {"id": m.ontology_node_id, "name": node_map[m.ontology_node_id]["name"]}
        for m in mappings
        if m.ontology_node_id in node_map
    ]

    return EngineerViewData(
        nodes=nodes_brief,
        mappings=mappings,
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
