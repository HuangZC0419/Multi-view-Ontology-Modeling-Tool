from __future__ import annotations

import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# PyInstaller 兼容：frozen 模式下使用 exe 所在目录作为数据根目录
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

PROJECTS_DIR = BASE_DIR / "projects"
INDEX_FILE = PROJECTS_DIR / "index.json"

if getattr(sys, "frozen", False):
    FRONTEND_DIST = Path(sys._MEIPASS) / "frontend" / "dist"
else:
    FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

_active_project_id: Optional[str] = None


class OntologyNode(BaseModel):
    id: str
    name: str = Field(min_length=1)
    x: float
    y: float
    parent_id: str | None = None
    attributes: list[dict[str, str]] = Field(default_factory=list)


class OntologyEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str = Field(min_length=1)
    kind: Literal["parent-child", "relation"]
    characteristics: list[str] = Field(default_factory=list)
    weight: float | None = None


class InferenceRule(BaseModel):
    id: str
    rel1: str
    rel2: str
    inferred_rel: str


class MutexRule(BaseModel):
    id: str
    rel1: str
    rel2: str


class GraphState(BaseModel):
    nodes: list[OntologyNode] = Field(default_factory=list)
    edges: list[OntologyEdge] = Field(default_factory=list)
    inference_rules: list[InferenceRule] = Field(default_factory=list)
    mutex_rules: list[MutexRule] = Field(default_factory=list)
    relation_weights: dict[str, float] = Field(default_factory=dict)


class CreateNodePayload(BaseModel):
    name: str = Field(min_length=1)
    x: float
    y: float
    parent_id: str | None = None
    attributes: list[dict[str, str]] = Field(default_factory=list)


class CreateEdgePayload(BaseModel):
    source: str
    target: str
    relation: str = Field(min_length=1)
    kind: Literal["parent-child", "relation"] = "relation"
    characteristics: list[str] = Field(default_factory=list)


class ReparentNodePayload(BaseModel):
    new_parent_id: str | None = None


class ProjectInfo(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str


class CreateProjectPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RenameProjectPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PathInfo(BaseModel):
    path: str
    probability: float


class UpstreamFactor(BaseModel):
    factor: str
    factor_id: str
    paths: list[PathInfo]
    combined_probability: float
    level: str  # "很高" "高" "中等" "较低"


class UpstreamResponse(BaseModel):
    target: str
    target_id: str
    factors: list[UpstreamFactor]


class DownstreamEffect(BaseModel):
    target: str
    target_id: str
    paths: list[PathInfo]
    combined_probability: float
    level: str


class DownstreamResponse(BaseModel):
    source: str
    source_id: str
    effects: list[DownstreamEffect]


class InfluenceRankItem(BaseModel):
    node: str
    node_id: str
    score: float
    reachable_nodes: int


class VulnerabilityItem(BaseModel):
    node: str
    node_id: str
    incoming_links: int


class OverviewResponse(BaseModel):
    influence_ranking: list[InfluenceRankItem]
    vulnerability_ranking: list[VulnerabilityItem]
    strongest_paths: list[PathInfo]
    summary: str


class WeightConfigPayload(BaseModel):
    relation_weights: dict[str, float]


app = FastAPI(title="Ontology Canvas API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.routers.datasource import router as datasource_router
from app.routers.perspective import router as perspective_router

app.include_router(datasource_router)
app.include_router(perspective_router)


# ============================================================
# 多项目管理：辅助函数
# ============================================================

def _ensure_projects_dir() -> None:
    """确保 projects/ 目录和 index.json 存在"""
    if not PROJECTS_DIR.exists():
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text("[]", encoding="utf-8")


def _load_project_index() -> list[dict]:
    """加载项目索引列表"""
    _ensure_projects_dir()
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_project_index(projects: list[dict]) -> None:
    """保存项目索引列表"""
    _ensure_projects_dir()
    INDEX_FILE.write_text(
        json.dumps(projects, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _project_file_path(project_id: str) -> Path:
    return PROJECTS_DIR / f"{project_id}.json"


def _load_project_data(project_id: str) -> GraphState:
    """从文件加载指定项目的图数据"""
    data_file = _project_file_path(project_id)
    if not data_file.exists():
        return GraphState()
    try:
        raw = json.loads(data_file.read_text(encoding="utf-8"))
        return GraphState.model_validate(raw)
    except Exception:
        return GraphState()


def _save_project_data(project_id: str, graph: GraphState) -> None:
    """将图数据保存到指定项目文件，并更新索引中的 updated_at"""
    _ensure_projects_dir()
    _project_file_path(project_id).write_text(
        json.dumps(graph.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 同步更新索引中的更新时间
    projects = _load_project_index()
    now = datetime.utcnow().isoformat()
    found = False
    for p in projects:
        if p["id"] == project_id:
            p["updated_at"] = now
            found = True
            break
    if found:
        _save_project_index(projects)


def _migrate_old_data() -> str | None:
    """从旧 data.json 迁移数据到项目存储，返回默认项目 ID，无数据则返回 None"""
    old_data_file = Path(__file__).resolve().parent.parent / "data.json"
    if not old_data_file.exists():
        return None

    try:
        raw = json.loads(old_data_file.read_text(encoding="utf-8"))
        graph = GraphState.model_validate(raw)
    except Exception:
        return None

    # 检查是否有实际内容需要迁移
    if not graph.nodes and not graph.edges and not graph.inference_rules and not graph.mutex_rules:
        return None

    # 创建默认项目并导入数据
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    default_project = {
        "id": project_id,
        "name": "默认项目",
        "created_at": now,
        "updated_at": now,
    }
    projects = _load_project_index()
    projects.append(default_project)
    _save_project_index(projects)
    _save_project_data(project_id, graph)

    # 迁移完成后删除旧文件
    try:
        old_data_file.unlink()
    except Exception:
        pass

    return project_id


_BUNDLED_PROJECT_NAMES = {
    "machining-demo": "机械加工工艺案例",
}


def _import_bundled_projects() -> None:
    """从 PyInstaller 打包数据中导入预置项目（仅 frozen 模式生效）"""
    if not getattr(sys, "frozen", False):
        return
    bundled_dir = Path(sys._MEIPASS) / "projects"
    if not bundled_dir.is_dir():
        return

    projects = _load_project_index()
    existing_ids = {p["id"] for p in projects}
    imported = False

    for f in sorted(bundled_dir.glob("*.json")):
        if f.name == "index.json":
            continue
        project_id = f.stem
        if project_id in existing_ids:
            continue
        target = _project_file_path(project_id)
        if target.exists():
            continue
        target.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        now = datetime.utcnow().isoformat()
        projects.append({
            "id": project_id,
            "name": _BUNDLED_PROJECT_NAMES.get(project_id, project_id),
            "created_at": now,
            "updated_at": now,
        })
        existing_ids.add(project_id)
        imported = True

    if imported:
        _save_project_index(projects)


def _init_default_project() -> str:
    """初始化默认项目（不存在任何项目时创建），返回默认项目 ID"""
    projects = _load_project_index()
    if projects:
        _import_bundled_projects()
        return projects[0]["id"]

    # 尝试从旧 data.json 迁移
    migrated_id = _migrate_old_data()
    if migrated_id:
        _import_bundled_projects()
        return migrated_id

    # 无旧数据，创建全新的默认项目
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    default_project = {
        "id": project_id,
        "name": "默认项目",
        "created_at": now,
        "updated_at": now,
    }
    projects.append(default_project)
    _save_project_index(projects)
    _save_project_data(project_id, GraphState())

    # 导入预置案例项目
    _import_bundled_projects()

    return project_id


def load_graph() -> GraphState:
    """加载活跃项目的图数据（首次调用时自动初始化默认项目）"""
    global _active_project_id
    if _active_project_id is None:
        _active_project_id = _init_default_project()
    return _load_project_data(_active_project_id)


def save_graph(graph: GraphState) -> None:
    """保存图数据至活跃项目文件"""
    global _active_project_id
    if _active_project_id is None:
        _active_project_id = _init_default_project()
    _save_project_data(_active_project_id, graph)


graph_state = load_graph()


@app.get("/api/graph", response_model=GraphState)
def get_graph(project_id: str = Query(..., description="项目 ID（必填）")) -> GraphState:
    global _active_project_id, graph_state
    # 校验项目存在
    projects = _load_project_index()
    if not any(p["id"] == project_id for p in projects):
        raise HTTPException(status_code=400, detail="指定项目不存在")
    _active_project_id = project_id
    graph_state = _load_project_data(project_id)
    return graph_state


@app.put("/api/graph", response_model=GraphState)
def replace_graph(
    payload: GraphState,
    project_id: str = Query(..., description="项目 ID（必填）"),
) -> GraphState:
    global _active_project_id, graph_state
    # 校验项目存在
    projects = _load_project_index()
    if not any(p["id"] == project_id for p in projects):
        raise HTTPException(status_code=400, detail="指定项目不存在")
    _active_project_id = project_id
    graph_state = payload
    _save_project_data(project_id, graph_state)
    return graph_state


@app.post("/api/nodes", response_model=OntologyNode)
def create_node(payload: CreateNodePayload) -> OntologyNode:
    if payload.parent_id and not any(n.id == payload.parent_id for n in graph_state.nodes):
        raise HTTPException(status_code=400, detail="parent_id 对应节点不存在")

    node = OntologyNode(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        x=payload.x,
        y=payload.y,
        parent_id=payload.parent_id,
    )
    graph_state.nodes.append(node)

    if payload.parent_id:
        parent_edge = OntologyEdge(
            id=str(uuid.uuid4()),
            source=payload.parent_id,
            target=node.id,
            relation="父子关系",
            kind="parent-child",
        )
        graph_state.edges.append(parent_edge)

    save_graph(graph_state)
    return node


@app.post("/api/edges", response_model=OntologyEdge)
def create_edge(payload: CreateEdgePayload) -> OntologyEdge:
    if payload.source == payload.target:
        raise HTTPException(status_code=400, detail="不能连接到自身")

    all_ids = {n.id for n in graph_state.nodes}
    if payload.source not in all_ids or payload.target not in all_ids:
        raise HTTPException(status_code=400, detail="source 或 target 节点不存在")

    relation_clean = payload.relation.strip()

    # 1. 互斥规则检查（有向关系：仅检查同一方向 source→target）
    existing_edges = [
        e for e in graph_state.edges
        if e.source == payload.source and e.target == payload.target
    ]
    existing_rels = {e.relation for e in existing_edges}

    for rule in graph_state.mutex_rules:
        if relation_clean == rule.rel1 and rule.rel2 in existing_rels:
            raise HTTPException(status_code=400, detail=f"互斥约束冲突：无法在已有 '{rule.rel2}' 关系上建立 '{rule.rel1}'")
        if relation_clean == rule.rel2 and rule.rel1 in existing_rels:
            raise HTTPException(status_code=400, detail=f"互斥约束冲突：无法在已有 '{rule.rel1}' 关系上建立 '{rule.rel2}'")

    edge = OntologyEdge(
        id=str(uuid.uuid4()),
        source=payload.source,
        target=payload.target,
        relation=relation_clean,
        kind=payload.kind,
    )
    graph_state.edges.append(edge)
    
    # 2. 顺承/推理规则自动连线 (简单的 BFS 传播)
    edges_to_process = [edge]
    # 使用 signature 避免重复添加和无限循环
    seen_signatures = {(e.source, e.target, e.relation) for e in graph_state.edges}

    while edges_to_process:
        curr = edges_to_process.pop(0)

        for rule in graph_state.inference_rules:
            # 模式 A: curr 作为 rel1 (A -> B)，寻找 B -> C 的 rel2
            if curr.relation == rule.rel1:
                for e in graph_state.edges:
                    if e.source == curr.target and e.relation == rule.rel2:
                        sig = (curr.source, e.target, rule.inferred_rel)
                        if sig not in seen_signatures and curr.source != e.target:
                            inferred_edge = OntologyEdge(
                                id=str(uuid.uuid4()),
                                source=curr.source,
                                target=e.target,
                                relation=rule.inferred_rel,
                                kind="relation"
                            )
                            graph_state.edges.append(inferred_edge)
                            edges_to_process.append(inferred_edge)
                            seen_signatures.add(sig)

            # 模式 B: curr 作为 rel2 (B -> C)，寻找 A -> B 的 rel1
            if curr.relation == rule.rel2:
                for e in graph_state.edges:
                    if e.target == curr.source and e.relation == rule.rel1:
                        sig = (e.source, curr.target, rule.inferred_rel)
                        if sig not in seen_signatures and e.source != curr.target:
                            inferred_edge = OntologyEdge(
                                id=str(uuid.uuid4()),
                                source=e.source,
                                target=curr.target,
                                relation=rule.inferred_rel,
                                kind="relation"
                            )
                            graph_state.edges.append(inferred_edge)
                            edges_to_process.append(inferred_edge)
                            seen_signatures.add(sig)

    save_graph(graph_state)
    return edge


@app.post("/api/nodes/{node_id}/reparent", response_model=OntologyNode)
def reparent_node(node_id: str, payload: ReparentNodePayload) -> OntologyNode:
    node_map = {n.id: n for n in graph_state.nodes}
    node = node_map.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    if payload.new_parent_id == node_id:
        raise HTTPException(status_code=400, detail="不能将节点设置为自身的子节点")

    if payload.new_parent_id and payload.new_parent_id not in node_map:
        raise HTTPException(status_code=400, detail="new_parent_id 对应节点不存在")

    # 防止环：新父节点不能是当前节点的后代
    probe_id = payload.new_parent_id
    while probe_id:
        if probe_id == node_id:
            raise HTTPException(status_code=400, detail="不能将节点挂载到其后代节点下")
        probe = node_map.get(probe_id)
        probe_id = probe.parent_id if probe else None

    node.parent_id = payload.new_parent_id

    graph_state.edges = [
        edge
        for edge in graph_state.edges
        if not (edge.kind == "parent-child" and edge.target == node_id)
    ]

    if payload.new_parent_id:
        graph_state.edges.append(
            OntologyEdge(
                id=str(uuid.uuid4()),
                source=payload.new_parent_id,
                target=node_id,
                relation="父子关系",
                kind="parent-child",
            )
        )

    save_graph(graph_state)
    return node


# ============================================================
# 项目管理 API
# ============================================================

@app.get("/api/projects", response_model=List[ProjectInfo])
def list_projects() -> List[ProjectInfo]:
    projects = _load_project_index()
    return [
        ProjectInfo(
            id=p["id"],
            name=p["name"],
            created_at=p["created_at"],
            updated_at=p["updated_at"],
        )
        for p in projects
    ]


@app.post("/api/projects", response_model=ProjectInfo, status_code=201)
def create_project(payload: CreateProjectPayload) -> ProjectInfo:
    projects = _load_project_index()
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    new_project = {
        "id": project_id,
        "name": payload.name.strip(),
        "created_at": now,
        "updated_at": now,
    }
    projects.append(new_project)
    _save_project_index(projects)
    _save_project_data(project_id, GraphState())
    return ProjectInfo(
        id=new_project["id"],
        name=new_project["name"],
        created_at=new_project["created_at"],
        updated_at=new_project["updated_at"],
    )


@app.put("/api/projects/{project_id}", response_model=ProjectInfo)
def rename_project(project_id: str, payload: RenameProjectPayload) -> ProjectInfo:
    projects = _load_project_index()
    target_project = None
    for p in projects:
        if p["id"] == project_id:
            target_project = p
            break
    if target_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    now = datetime.utcnow().isoformat()
    target_project["name"] = payload.name.strip()
    target_project["updated_at"] = now
    _save_project_index(projects)
    return ProjectInfo(
        id=target_project["id"],
        name=target_project["name"],
        created_at=target_project["created_at"],
        updated_at=target_project["updated_at"],
    )


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    global _active_project_id, graph_state

    projects = _load_project_index()
    if len(projects) <= 1:
        raise HTTPException(status_code=400, detail="至少需要保留一个项目，无法删除")

    target_idx = None
    for idx, p in enumerate(projects):
        if p["id"] == project_id:
            target_idx = idx
            break
    if target_idx is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 从索引中移除
    removed_project = projects.pop(target_idx)
    _save_project_index(projects)

    # 删除项目数据文件
    data_file = _project_file_path(project_id)
    try:
        if data_file.exists():
            data_file.unlink()
    except Exception:
        pass

    # 如果删除的是当前活跃项目，切换到第一个可用项目
    if _active_project_id == project_id:
        new_active_id = projects[0]["id"]
        _active_project_id = new_active_id
        graph_state = _load_project_data(new_active_id)


# ============================================================
# 用户认证
# ============================================================

import openpyxl

USERS_XLSX = BASE_DIR / "users.xlsx"
_auth_sessions: dict[str, dict] = {}  # {token: {username, name, role}}


def _load_users() -> list[dict]:
    """从 users.xlsx 加载用户列表（username/password 均转为字符串）"""
    if not USERS_XLSX.exists():
        return []
    wb = openpyxl.load_workbook(str(USERS_XLSX), read_only=True, data_only=True)
    ws = wb.active
    users = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and row[1]:
            users.append({
                "username": str(row[0]).strip(),
                "password": str(int(row[1])) if isinstance(row[1], (int, float)) else str(row[1]).strip(),
                "role": str(row[2]).strip() if row[2] else "user",
                "name": str(row[3]).strip() if row[3] else str(row[0]).strip(),
            })
    wb.close()
    return users


class LoginPayload(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str = ""
    token: str | None = None
    username: str | None = None
    name: str | None = None
    role: str | None = None


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(payload: LoginPayload):
    users = _load_users()
    pw_str = str(payload.password).strip()
    uname_str = payload.username.strip()
    for u in users:
        if u["username"] == uname_str and u["password"] == pw_str:
            token = str(uuid.uuid4())
            _auth_sessions[token] = {
                "username": u["username"],
                "name": u["name"],
                "role": u["role"],
            }
            return LoginResponse(
                success=True, token=token,
                username=u["username"], name=u["name"], role=u["role"]
            )
    return LoginResponse(success=False, message="用户名或密码错误")


@app.post("/api/auth/logout")
async def logout(token: str = ""):
    _auth_sessions.pop(token, None)
    return {"success": True}


@app.get("/api/auth/session")
async def get_session(token: str = ""):
    """校验 token 是否有效，返回用户信息"""
    if token in _auth_sessions:
        return {"valid": True, **_auth_sessions[token]}
    return {"valid": False}


# ============================================================
# 贝叶斯网络影响分析
# ============================================================

def _get_edge_weight(edge: OntologyEdge, relation_weights: dict[str, float]) -> float:
    """获取边的因果权重"""
    if edge.weight is not None:
        return edge.weight  # 显式覆盖
    return relation_weights.get(edge.relation, 0.5)  # 默认映射，兜底0.5


def _build_expanded_adjacency(
    edges: list[OntologyEdge],
    inference_rules: list[InferenceRule],
    relation_weights: dict[str, float],
) -> tuple[dict[str, list[tuple[str, str, float, bool]]], set[tuple[str, str, str]]]:
    """构建扩展有向图邻接表，包含推理规则推导的间接边。

    返回:
        (adjacency, triggered_rules)
        adjacency: {source_id: [(target_id, relation, probability, is_derived), ...]}
        triggered_rules: {(rel1, rel2, inferred_rel), ...} 实际触发的规则集合
    """
    adj: dict[str, list[tuple[str, str, float, bool]]] = defaultdict(list)
    triggered: set[tuple[str, str, str]] = set()

    # 1. 添加所有显式关系边（排除 parent-child）
    for e in edges:
        if e.kind == "relation":
            prob = _get_edge_weight(e, relation_weights)
            adj[e.source].append((e.target, e.relation, prob, False))

    # 2. 迭代应用推理规则直到无新边产生（最多 10 轮防止无限循环）
    for _ in range(10):
        added_any = False
        for rule in inference_rules:
            for src_id, targets in list(adj.items()):
                for tgt_id, rel1, prob1, _ in targets:
                    if rel1 != rule.rel1:
                        continue
                    for tgt2_id, rel2, prob2, _ in adj.get(tgt_id, []):
                        if rel2 != rule.rel2:
                            continue
                        if src_id == tgt2_id:
                            continue  # 不允许自环
                        # 检查是否已存在相同的关系边
                        existing = {(t, r) for t, r, _p, _d in adj.get(src_id, [])}
                        if (tgt2_id, rule.inferred_rel) in existing:
                            continue
                        inferred_prob = prob1 * prob2
                        adj[src_id].append(
                            (tgt2_id, rule.inferred_rel, inferred_prob, True)
                        )
                        triggered.add((rule.rel1, rule.rel2, rule.inferred_rel))
                        added_any = True
        if not added_any:
            break

    return adj, triggered


def _find_all_paths(
    adj: dict[str, list[tuple[str, str, float, bool]]],
    start: str,
    end: str,
    max_paths: int = 30,
) -> list[tuple[list[str], list[str], list[float], float]]:
    """DFS 深度优先搜索从 start 到 end 的所有简单路径（不重复节点）。

    返回:
        [(node_path, relation_path, prob_list, path_probability), ...]
        按路径概率降序排列
    """
    all_paths: list[tuple[list[str], list[str], list[float], float]] = []

    def dfs(
        current: str,
        nodes_visited: list[str],
        rels_visited: list[str],
        probs_visited: list[float],
    ) -> None:
        if len(all_paths) >= max_paths:
            return
        if current == end and len(rels_visited) > 0:
            path_prob = 1.0
            for p in probs_visited:
                path_prob *= p
            all_paths.append((
                list(nodes_visited),
                list(rels_visited),
                list(probs_visited),
                round(path_prob, 6),
            ))
            return
        if current not in adj:
            return
        for next_node, relation, prob, _ in adj[current]:
            if next_node not in nodes_visited:
                dfs(
                    next_node,
                    nodes_visited + [next_node],
                    rels_visited + [relation],
                    probs_visited + [prob],
                )

    dfs(start, [start], [], [])

    # 按概率降序排序
    all_paths.sort(key=lambda x: x[3], reverse=True)
    return all_paths


def _noisy_or(probabilities: list[float]) -> float:
    """Noisy-OR 模型合并多条独立路径概率。

    P_combined = 1 - prod(1 - P_i)
    """
    if not probabilities:
        return 0.0
    result = 1.0
    for p in probabilities:
        result *= (1.0 - p)
    return round(1.0 - result, 4)


def _cumulative_level(prob: float) -> str:
    """将概率值映射为影响力等级"""
    if prob >= 0.8:
        return "很高"
    if prob >= 0.6:
        return "高"
    if prob >= 0.4:
        return "中等"
    return "较低"


def _format_path_string(
    node_path: list[str],
    rel_path: list[str],
    id_to_name: dict[str, str],
) -> str:
    """将路径格式化为可读的中文展示字符串。

    示例: 预热温度→控制→精馏塔→产生→塔顶产物→决定→产品纯度
    """
    parts: list[str] = []
    for i, node_id in enumerate(node_path):
        parts.append(id_to_name.get(node_id, node_id))
        if i < len(rel_path):
            parts.append(rel_path[i])
    return "→".join(parts)


@app.get("/api/bayesian/trace-upstream/{project_id}", response_model=UpstreamResponse)
def trace_upstream(
    project_id: str,
    target: str = Query(..., description="目标节点ID"),
) -> UpstreamResponse:
    """向上追溯：DFS 找出所有能到达目标节点的上游因子，计算因果路径概率。

    对目标节点，找出所有能到达它的上游因子，计算每条因果路径的概率。
    路径概率 = 路径上所有边权重的乘积，多路径合并 = Noisy-OR。
    """
    # 1. 验证项目存在
    projects = _load_project_index()
    if not any(p["id"] == project_id for p in projects):
        raise HTTPException(status_code=400, detail="指定项目不存在")

    # 2. 加载项目图数据
    graph = _load_project_data(project_id)
    if not graph.nodes:
        raise HTTPException(status_code=400, detail="项目数据为空，无法进行贝叶斯分析")

    nodes = graph.nodes
    edges = graph.edges
    inference_rules = graph.inference_rules
    relation_weights = graph.relation_weights

    id_to_name: dict[str, str] = {n.id: n.name for n in nodes}

    # 3. 验证目标节点存在
    if target not in id_to_name:
        raise HTTPException(status_code=400, detail=f"目标节点 '{target}' 不存在")
    target_name = id_to_name[target]

    # 4. 构建扩展有向图
    adj, _ = _build_expanded_adjacency(edges, inference_rules, relation_weights)

    # 5. 找出所有能到达目标的上游因子
    factors: list[UpstreamFactor] = []
    for node in nodes:
        if node.id == target:
            continue

        paths = _find_all_paths(adj, node.id, target)
        if not paths:
            continue

        # 提取各路径概率（已排序，第一条即最佳路径）
        path_probabilities = [p[3] for p in paths]

        # Noisy-OR 合并所有路径
        combined_prob = _noisy_or(path_probabilities)

        # 影响力等级
        level = _cumulative_level(combined_prob)

        # 格式化所有路径
        formatted_paths: list[PathInfo] = []
        for node_path, rel_path, _, prob in paths:
            formatted_paths.append(PathInfo(
                path=_format_path_string(node_path, rel_path, id_to_name),
                probability=round(prob, 4),
            ))

        factors.append(UpstreamFactor(
            factor=node.name,
            factor_id=node.id,
            paths=formatted_paths,
            combined_probability=combined_prob,
            level=level,
        ))

    # 按合并概率降序排列
    factors.sort(key=lambda f: f.combined_probability, reverse=True)

    return UpstreamResponse(
        target=target_name,
        target_id=target,
        factors=factors,
    )


@app.get("/api/bayesian/propagate-downstream/{project_id}", response_model=DownstreamResponse)
def propagate_downstream(
    project_id: str,
    source: str = Query(..., description="源节点ID"),
) -> DownstreamResponse:
    """向下传播：BFS 找出源节点能影响的所有下游节点。

    从因子节点出发，找出它能影响的所有下游节点及每条因果路径的概率。
    """
    # 1. 验证项目存在
    projects = _load_project_index()
    if not any(p["id"] == project_id for p in projects):
        raise HTTPException(status_code=400, detail="指定项目不存在")

    # 2. 加载项目图数据
    graph = _load_project_data(project_id)
    if not graph.nodes:
        raise HTTPException(status_code=400, detail="项目数据为空，无法进行贝叶斯分析")

    nodes = graph.nodes
    edges = graph.edges
    inference_rules = graph.inference_rules
    relation_weights = graph.relation_weights

    id_to_name: dict[str, str] = {n.id: n.name for n in nodes}

    # 3. 验证源节点存在
    if source not in id_to_name:
        raise HTTPException(status_code=400, detail=f"源节点 '{source}' 不存在")
    source_name = id_to_name[source]

    # 4. 构建扩展有向图
    adj, _ = _build_expanded_adjacency(edges, inference_rules, relation_weights)

    # 5. BFS 找出所有能从源节点到达的下游节点
    reachable_ids: set[str] = set()
    queue = [source]
    while queue:
        current = queue.pop(0)
        for next_node, _rel, _prob, _derived in adj.get(current, []):
            if next_node not in reachable_ids and next_node != source:
                reachable_ids.add(next_node)
                queue.append(next_node)

    # 6. 对每个可达下游节点计算影响
    effects: list[DownstreamEffect] = []
    for target_id in reachable_ids:
        paths = _find_all_paths(adj, source, target_id)
        if not paths:
            continue

        path_probabilities = [p[3] for p in paths]
        combined_prob = _noisy_or(path_probabilities)
        level = _cumulative_level(combined_prob)

        formatted_paths: list[PathInfo] = []
        for node_path, rel_path, _, prob in paths:
            formatted_paths.append(PathInfo(
                path=_format_path_string(node_path, rel_path, id_to_name),
                probability=round(prob, 4),
            ))

        effects.append(DownstreamEffect(
            target=id_to_name.get(target_id, target_id),
            target_id=target_id,
            paths=formatted_paths,
            combined_probability=combined_prob,
            level=level,
        ))

    # 按合并概率降序排列
    effects.sort(key=lambda e: e.combined_probability, reverse=True)

    return DownstreamResponse(
        source=source_name,
        source_id=source,
        effects=effects,
    )


@app.get("/api/bayesian/overview/{project_id}", response_model=OverviewResponse)
def bayesian_overview(project_id: str) -> OverviewResponse:
    """全局概览：分析整个网络的影响力排名、脆弱性排名和最强因果链。

    返回影响力排名（综合下游影响范围）、最脆弱节点（最多上游依赖）、
    最强因果链（概率最高的跨越多节点的路径）。
    """
    # 1. 验证项目存在
    projects = _load_project_index()
    if not any(p["id"] == project_id for p in projects):
        raise HTTPException(status_code=400, detail="指定项目不存在")

    # 2. 加载项目图数据
    graph = _load_project_data(project_id)
    if not graph.nodes:
        raise HTTPException(status_code=400, detail="项目数据为空，无法进行贝叶斯分析")

    nodes = graph.nodes
    edges = graph.edges
    inference_rules = graph.inference_rules
    relation_weights = graph.relation_weights

    id_to_name: dict[str, str] = {n.id: n.name for n in nodes}
    all_node_ids = set(id_to_name.keys())

    # 3. 构建扩展有向图
    adj, _ = _build_expanded_adjacency(edges, inference_rules, relation_weights)

    # 4. 影响力排名：对每个节点，BFS 计算可达节点数，score = 最大出边权重
    influence_ranking: list[InfluenceRankItem] = []
    for node in nodes:
        if node.id not in adj:
            influence_ranking.append(InfluenceRankItem(
                node=node.name,
                node_id=node.id,
                score=0.0,
                reachable_nodes=0,
            ))
            continue

        # BFS 计算可达节点数
        visited: set[str] = {node.id}
        queue = [node.id]
        while queue:
            current = queue.pop(0)
            for next_node, _rel, _prob, _derived in adj.get(current, []):
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append(next_node)

        reachable_count = len(visited) - 1  # 排除自身

        # score = 最大出边权重
        max_out_weight = max((prob for _, _, prob, _ in adj[node.id]), default=0.0)

        influence_ranking.append(InfluenceRankItem(
            node=node.name,
            node_id=node.id,
            score=round(max_out_weight, 4),
            reachable_nodes=reachable_count,
        ))

    # 按 score 降序排列
    influence_ranking.sort(key=lambda x: (x.score, x.reachable_nodes), reverse=True)

    # 5. 脆弱性排名：统计每个节点的入边数量
    incoming_counts: dict[str, int] = defaultdict(int)
    for nid in all_node_ids:
        incoming_counts[nid] = 0
    for src_id, targets in adj.items():
        for tgt_id, _rel, _prob, _derived in targets:
            incoming_counts[tgt_id] += 1

    vulnerability_ranking: list[VulnerabilityItem] = []
    for node in nodes:
        vulnerability_ranking.append(VulnerabilityItem(
            node=node.name,
            node_id=node.id,
            incoming_links=incoming_counts.get(node.id, 0),
        ))

    # 按入边数量降序排列
    vulnerability_ranking.sort(key=lambda x: x.incoming_links, reverse=True)

    # 6. 最强因果链：从影响力排名前10的节点出发，寻找跨越多节点的长路径
    strongest_paths: list[PathInfo] = []
    top_influencers = [item for item in influence_ranking[:10] if item.reachable_nodes >= 1]

    all_path_candidates: list[tuple[str, float]] = []
    for influencer in top_influencers:
        src_id = influencer.node_id
        # BFS找到该节点能到达的所有目标
        reachable: set[str] = set()
        queue = [src_id]
        while queue:
            current = queue.pop(0)
            for next_node, _rel, _prob, _derived in adj.get(current, []):
                if next_node not in reachable and next_node != src_id:
                    reachable.add(next_node)
                    queue.append(next_node)

        # 对每个可达目标，找概率最高的路径
        for tgt_id in reachable:
            paths = _find_all_paths(adj, src_id, tgt_id, max_paths=3)
            if paths:
                node_path, rel_path, _, prob = paths[0]
                # 只保留跨越至少一个中间节点的路径（长度 >= 2）
                if len(node_path) >= 3:
                    path_str = _format_path_string(node_path, rel_path, id_to_name)
                    all_path_candidates.append((path_str, prob))

    # 按概率降序，取前10条
    all_path_candidates.sort(key=lambda x: x[1], reverse=True)
    for path_str, prob in all_path_candidates[:10]:
        strongest_paths.append(PathInfo(path=path_str, probability=round(prob, 4)))

    # 7. 生成总结文本（完全通用）
    summary_parts: list[str] = []
    if influence_ranking:
        top_influencer = influence_ranking[0]
        summary_parts.append(
            f"在全网分析中，'{top_influencer.node}'具有最高影响力"
            f"（出边权重{top_influencer.score}，可影响{top_influencer.reachable_nodes}个节点）"
        )
    if vulnerability_ranking:
        top_vuln = vulnerability_ranking[0]
        summary_parts.append(
            f"'{top_vuln.node}'是最脆弱的节点（{top_vuln.incoming_links}条入边依赖）"
        )
    if strongest_paths:
        best = strongest_paths[0]
        summary_parts.append(
            f"最强因果链为'{best.path}'（概率{best.probability}）"
        )

    summary = "。".join(summary_parts) + "。" if summary_parts else "该本体网络的全局贝叶斯分析已完成。"

    return OverviewResponse(
        influence_ranking=influence_ranking,
        vulnerability_ranking=vulnerability_ranking,
        strongest_paths=strongest_paths,
        summary=summary,
    )


@app.put("/api/bayesian/weights/{project_id}")
def update_weights(project_id: str, payload: WeightConfigPayload) -> dict[str, str]:
    """更新项目的贝叶斯关系权重配置。

    保存到项目的 relation_weights 字段。
    """
    # 1. 验证项目存在
    projects = _load_project_index()
    if not any(p["id"] == project_id for p in projects):
        raise HTTPException(status_code=400, detail="指定项目不存在")

    # 2. 加载项目图数据
    graph = _load_project_data(project_id)

    # 3. 更新权重
    graph.relation_weights = payload.relation_weights
    _save_project_data(project_id, graph)

    # 4. 同步更新全局状态（如果当前活跃项目恰好是该项目）
    global _active_project_id, graph_state
    if _active_project_id == project_id:
        graph_state = graph

    return {"status": "ok", "message": "权重配置已更新"}


# ============================================================
# 前端静态文件服务（仅在 dist 目录存在时启用）
# ============================================================
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    # 支持直接用 python main.py 运行
    uvicorn.run(app, host="0.0.0.0", port=8000)
