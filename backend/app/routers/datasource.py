"""数据源接入 API -- 数据库连接 + 文件上传 + 本体导入"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.models import ImportSelection
from app.connectors.dameng import SimDamengConnector, DamengConnector
from app.connectors.file_parser import FileParserConnector
from app.services.ontology_extract import extract_ontology_nodes, extract_ontology_from_data

router = APIRouter(prefix="/api/datasource")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

_sessions: dict[str, tuple] = {}


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _upload_meta_path(file_id: str) -> Path:
    return UPLOAD_DIR / f"{file_id}.meta.json"


def _save_upload_meta(file_id: str, file_name: str, file_type: str) -> None:
    _upload_meta_path(file_id).write_text(
        json.dumps({
            "file_name": file_name,
            "file_type": file_type,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_upload_meta(file_id: str) -> dict:
    meta_path = _upload_meta_path(file_id)
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ============================================================
# 数据库连接
# ============================================================

@router.post("/db/test")
async def test_db_connection(config: dict):
    """测试数据库连接参数"""
    db_type = config.get("type", "sim_dameng")
    if db_type == "dameng":
        connector = DamengConnector()
    else:
        connector = SimDamengConnector()
    ok = await connector.test_connection(config)
    return {"success": ok, "message": "连接成功" if ok else "连接失败，请检查参数"}


@router.post("/db/connect")
async def connect_db(config: dict):
    """建立数据库连接，返回 session_id"""
    db_type = config.get("type", "sim_dameng")
    if db_type == "dameng":
        connector = DamengConnector()
    else:
        connector = SimDamengConnector()
    ok = await connector.connect(config)
    if not ok:
        raise HTTPException(500, "连接失败")
    session_id = str(uuid.uuid4())
    _sessions[session_id] = (connector, db_type)
    return {"session_id": session_id, "db_type": db_type}


@router.get("/db/tables")
async def get_db_tables(session_id: str):
    """获取表列表"""
    if session_id not in _sessions:
        raise HTTPException(404, "会话不存在或已过期")
    connector, _ = _sessions[session_id]
    tables = await connector.get_tables()
    return {"tables": [t.model_dump() for t in tables]}


@router.get("/db/tables/{table}/columns")
async def get_db_columns(table: str, session_id: str, schema: str = ""):
    """获取列信息"""
    if session_id not in _sessions:
        raise HTTPException(404, "会话不存在或已过期")
    connector, _ = _sessions[session_id]
    columns = await connector.get_columns(table, schema)
    return {"columns": [c.model_dump() for c in columns]}


@router.get("/db/tables/{table}/preview")
async def preview_db_data(table: str, session_id: str, schema: str = "", limit: int = 10):
    """预览表数据"""
    if session_id not in _sessions:
        raise HTTPException(404, "会话不存在或已过期")
    connector, _ = _sessions[session_id]
    rows = await connector.preview_data(table, schema, limit)
    return {"rows": rows}


@router.post("/db/disconnect")
async def disconnect_db(session_id: str):
    """断开数据库连接"""
    if session_id in _sessions:
        connector, _ = _sessions.pop(session_id)
        await connector.disconnect()
    return {"success": True}


# ============================================================
# 文件上传
# ============================================================

@router.post("/file/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 Excel/CSV 文件，返回解析后的结构"""
    _ensure_upload_dir()

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, f"不支持的文件格式: {ext}，仅支持 .xlsx .xls .csv")

    file_id = str(uuid.uuid4())
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    _save_upload_meta(file_id, file.filename or save_name, ext)

    parser = FileParserConnector()
    await parser.connect({"file_path": str(save_path), "file_type": ext})
    tables = await parser.get_tables()
    columns_map = {}
    for t in tables:
        cols = await parser.get_columns(t.name)
        columns_map[t.name] = [c.model_dump() for c in cols]
    await parser.disconnect()

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "file_type": ext,
        "tables": [t.model_dump() for t in tables],
        "columns": columns_map
    }


@router.get("/file/{file_id}/preview")
async def preview_file_data(file_id: str, table: str = "", limit: int = 10):
    """预览上传文件的数据"""
    _ensure_upload_dir()
    for ext in (".xlsx", ".xls", ".csv"):
        path = UPLOAD_DIR / f"{file_id}{ext}"
        if path.exists():
            parser = FileParserConnector()
            await parser.connect({"file_path": str(path), "file_type": ext})
            if table:
                rows = await parser.preview_data(table, limit=limit)
            else:
                tables = await parser.get_tables()
                rows = await parser.preview_data(tables[0].name, limit=limit) if tables else []
            await parser.disconnect()
            return {"rows": rows}
    raise HTTPException(404, "文件不存在或已过期")


# ============================================================
# 本体导入（数据库 + 文件共用）
# ============================================================

@router.post("/import")
async def import_ontology(selection: ImportSelection):
    """提交用户勾选，生成本体节点"""
    source_id = selection.source_id
    nodes = []
    edges = []
    inf_rules = []
    mut_rules = []

    # 检查是否为特殊的本体关系表模板
    is_template = "实体关系" in selection.tables or "实体属性" in selection.tables

    if source_id in _sessions:
        connector, db_type = _sessions[source_id]
        if is_template:
            relations_data = await connector.preview_data("实体关系", "", 10000) if "实体关系" in selection.tables else []
            attributes_data = await connector.preview_data("实体属性", "", 10000) if "实体属性" in selection.tables else []
            inference_data = await connector.preview_data("推理规则", "", 10000) if "推理规则" in selection.tables else []
            mutex_data = await connector.preview_data("互斥规则", "", 10000) if "互斥规则" in selection.tables else []
            nodes, edges, inf_rules, mut_rules = extract_ontology_from_data(relations_data, attributes_data, inference_data, mutex_data, source_name=db_type)
        else:
            tables = await connector.get_tables()
            columns_map = {}
            for t in tables:
                if t.name in selection.tables:
                    cols = await connector.get_columns(t.name)
                    columns_map[t.name] = cols
            nodes = extract_ontology_nodes(
                tables=tables,
                columns_map=columns_map,
                selection=selection,
                source_name=db_type
            )
    else:
        _ensure_upload_dir()
        for ext in (".xlsx", ".xls", ".csv"):
            path = UPLOAD_DIR / f"{source_id}{ext}"
            if path.exists():
                parser = FileParserConnector()
                await parser.connect({"file_path": str(path), "file_type": ext})
                origin_type = "csv" if ext == ".csv" else "excel"
                upload_meta = _load_upload_meta(source_id)
                original_file_name = upload_meta.get("file_name", "").strip()
                origin_name = f"{origin_type}:{original_file_name}" if original_file_name else origin_type
                
                if is_template:
                    relations_data = await parser.preview_data("实体关系", limit=10000) if "实体关系" in selection.tables else []
                    attributes_data = await parser.preview_data("实体属性", limit=10000) if "实体属性" in selection.tables else []
                    inference_data = await parser.preview_data("推理规则", limit=10000) if "推理规则" in selection.tables else []
                    mutex_data = await parser.preview_data("互斥规则", limit=10000) if "互斥规则" in selection.tables else []
                    nodes, edges, inf_rules, mut_rules = extract_ontology_from_data(relations_data, attributes_data, inference_data, mutex_data, source_name=origin_name)
                else:
                    tables = await parser.get_tables()
                    columns_map = {}
                    for t in tables:
                        if t.name in selection.tables:
                            cols = await parser.get_columns(t.name)
                            columns_map[t.name] = cols
                    nodes = extract_ontology_nodes(
                        tables=tables,
                        columns_map=columns_map,
                        selection=selection,
                        source_name=origin_name
                    )
                await parser.disconnect()
                break

    return {
        "nodes": nodes,
        "edges": edges,
        "inference_rules": inf_rules,
        "mutex_rules": mut_rules,
        "count": len(nodes)
    }
