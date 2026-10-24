"""通用 JSONL 标注数据解析与知识图谱构建。

兼容：字段别名、数字/字符串 id、行首脏前缀、同文件多行、
整文件 JSON 数组、id 或实体文本作为关系端点、实体与关系分行的导出格式。
跨记录关系按「记录内映射优先、同文件文件级映射其次」解析；
同一文件内重复 raw_id 时，文件级映射取首次出现。

节点 name 保留原始文本，不做 HTML 转义；HTML 安全显示由渲染层
（NodeCard.vue / App.vue）负责，避免污染检索、tooltip 与手工节点合并。
"""

from __future__ import annotations

import json
import math
import re
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FILE_LABEL = "文件"
DEFAULT_ENTITY_LABEL = "实体"
DEFAULT_RELATION = "关联"
CONTAIN_RELATION = "包含"

# 卡片尺寸与布局参数：200×88 对应前端 NodeCard.vue 的卡片尺寸。
# 注意：Task 6 为卡片增加标签条后，CARD_H 需要重新核对。
# 文件块按首次出现顺序纵向堆叠，实体在文件右侧按 4 列网格排列。
CARD_W = 200
CARD_H = 88
ENTITY_COLS = 4
ENTITY_DX = 240
ENTITY_DY = 120
ENTITY_START_X = 320
BLOCK_GAP = 80

FILE_NAME_KEYS = (
    "file_name", "fileName", "filename", "document_name", "doc_name",
    "source_file", "file", "文件名", "文档名", "文件",
)
# 强别名允许字符串元素；弱别名（labels/annotations）必须是带文本字段的对象
STRONG_ENTITY_ARRAY_KEYS = (
    "spans", "entities", "mentions", "ner", "实体", "标注片段",
)
WEAK_ENTITY_ARRAY_KEYS = ("labels", "annotations")
ENTITY_ARRAY_KEYS = STRONG_ENTITY_ARRAY_KEYS + WEAK_ENTITY_ARRAY_KEYS
RELATION_ARRAY_KEYS = (
    "relations", "links", "edges", "triples", "关系", "三元组",
)
ENTITY_TEXT_KEYS = (
    "text", "mention", "entity", "value", "surface", "word", "span_text", "实体名", "文本",
)
ENTITY_LABEL_KEYS = (
    "label", "type", "tag", "entity_type", "category", "标签", "类型",
)
ENTITY_ID_KEYS = ("id", "span_id", "ann_id", "key")
REL_FROM_KEYS = (
    "fromId", "from_id", "from", "source", "head", "subject", "subj", "head_id", "头实体",
)
REL_TO_KEYS = (
    "toId", "to_id", "to", "target", "tail", "object", "obj", "tail_id", "尾实体",
)
REL_TYPE_KEYS = ("type", "relation", "rel", "label", "predicate", "关系", "关系类型")

MAX_WARNINGS = 20
MAX_NESTED_DEPTH = 3
# 这些键下的数组通常存放元信息，不参与嵌套实体/关系识别
NON_DATA_LIST_KEYS = {"meta", "metadata", "sources"}


@dataclass
class JsonlParseResult:
    """JSONL 解析结果。

    total_lines：逐行模式下为非空行数，JSON 数组模式下为数组元素个数。
    bad_lines：逐行模式下为解析失败（含非对象）的行数，JSON 数组模式下为非对象元素个数。
    """

    records: list[dict] = field(default_factory=list)
    mappings: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    total_lines: int = 0
    bad_lines: int = 0


def _clean_text(value: str) -> str:
    """清除孤立代理字符等无法编码为 UTF-8 的内容。"""
    return value.encode("utf-8", "replace").decode("utf-8")


def _scalar_text(value) -> str:
    """只接受标量值，避免把 dict/list 强转成 repr。"""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    return _clean_text(str(value)).strip()


def _read_text(path) -> str:
    raw = Path(path).read_bytes()
    encodings = []
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings.append("utf-16")
    encodings.extend(("utf-8-sig", "utf-8", "gb18030"))
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _first_str_key(obj: dict, keys: tuple) -> str:
    """只接受非空字符串值，避免把嵌套对象误当成文件名。"""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return key
    return ""


def _first_scalar(obj: dict, keys: tuple):
    """按别名顺序返回第一个能产出非空标量的 (键, 值)。"""
    for key in keys:
        if key not in obj:
            continue
        text = _scalar_text(obj[key])
        if text:
            return key, text
    return "", ""


def _split_records(text: str):
    """返回 (records, bad_lines, total_lines, warnings)。"""
    warnings = []
    stripped = text.strip()
    bracket = stripped.find("[")
    brace = stripped.find("{")
    if bracket >= 0 and (brace < 0 or bracket < brace):
        try:
            data = json.loads(stripped[bracket:])
        except (ValueError, RecursionError):
            data = None
            warnings.append("文件疑似 JSON 数组但不是有效 JSON，已尝试按逐行模式解析")
        if isinstance(data, list):
            records = [item for item in data if isinstance(item, dict)]
            bad = len(data) - len(records)
            if bad:
                warnings.append(f"JSON 数组中有 {bad} 个元素不是对象，已跳过")
            if not data and len(warnings) < MAX_WARNINGS:
                warnings.append("文件为空或没有任何非空行")
            return records, bad, len(data), warnings

    records = []
    bad = 0
    total = 0
    for line_no, line in enumerate(text.split("\n"), start=1):
        line = line.rstrip("\r")
        if not line.strip():
            continue
        total += 1
        brace_at = line.find("{")
        candidate = line[brace_at:] if brace_at >= 0 else line
        try:
            obj = json.loads(candidate)
        except (ValueError, RecursionError):
            bad += 1
            if len(warnings) < MAX_WARNINGS:
                warnings.append(f"第 {line_no} 行不是有效 JSON，已跳过")
            continue
        if isinstance(obj, dict):
            records.append(obj)
        else:
            bad += 1
            if len(warnings) < MAX_WARNINGS:
                warnings.append(f"第 {line_no} 行不是 JSON 对象，已跳过")
    if total == 0:
        if len(warnings) < MAX_WARNINGS:
            warnings.append("文件为空或没有任何非空行")
    elif bad == total:
        # 全坏行时优先级最高，即使逐行告警已占满也要保留
        warnings.insert(0, "所有非空行均解析失败，疑似编码不匹配")
        del warnings[MAX_WARNINGS:]
    return records, bad, total, warnings


def _normalize_entity(
    item: Any,
    position: int,
    record_index: int,
    seen_raw_ids: set,
    warnings: list,
):
    if isinstance(item, str):
        text = _scalar_text(item)
        label = DEFAULT_ENTITY_LABEL
        raw_id = ""
    elif isinstance(item, dict):
        _, text = _first_scalar(item, ENTITY_TEXT_KEYS)
        _, label = _first_scalar(item, ENTITY_LABEL_KEYS)
        _, raw_id = _first_scalar(item, ENTITY_ID_KEYS)
    else:
        return None
    if not text:
        return None

    if raw_id:
        if raw_id in seen_raw_ids:
            if len(warnings) < MAX_WARNINGS:
                warnings.append(
                    f"第 {record_index + 1} 条记录：实体 id「{raw_id}」重复，已改用位置 id"
                )
            unique_id = f"{record_index}:pos:{position}"
        else:
            seen_raw_ids.add(raw_id)
            unique_id = f"{record_index}:id:{raw_id}"
    else:
        unique_id = f"{record_index}:pos:{position}"

    return {
        "id": unique_id,
        "raw_id": raw_id,
        "text": text,
        "label": label or DEFAULT_ENTITY_LABEL,
    }


def _extract_entities(record: dict):
    """按别名顺序返回第一个通过结构校验的非空数组。

    空数组或校验失败的数组视为不存在，以便后续别名或嵌套兜底接管。
    """
    for key in ENTITY_ARRAY_KEYS:
        value = record.get(key)
        if isinstance(value, list) and value and _valid_entity_array(value, key):
            return value, key
    return [], ""


def _extract_relations(record: dict):
    """按别名顺序返回第一个通过结构校验的非空数组。

    空数组或校验失败的数组视为不存在，以便后续别名或嵌套兜底接管。
    """
    for key in RELATION_ARRAY_KEYS:
        value = record.get(key)
        if isinstance(value, list) and value and _valid_relation_array(value, key):
            return value, key
    return [], ""


def _looks_like_entity(item: dict) -> bool:
    _, text = _first_scalar(item, ENTITY_TEXT_KEYS)
    _, label = _first_scalar(item, ENTITY_LABEL_KEYS)
    return bool(text and label)


def _looks_like_relation(item: dict) -> bool:
    _, source = _first_scalar(item, REL_FROM_KEYS)
    _, target = _first_scalar(item, REL_TO_KEYS)
    return bool(source and target)


def _join_path(path: str, key) -> str:
    """拼接映射路径，并清洗键名中的孤立代理字符。"""
    safe_key = _clean_text(str(key))
    return f"{path}.{safe_key}" if path else safe_key


def _iter_nested_dicts(container: dict, depth: int = 1, path: str = ""):
    """广度优先产出 (字典, 深度, 路径)，最多 MAX_NESTED_DEPTH 层。

    NON_DATA_LIST_KEYS 下的整棵子树（无论数组还是对象）都不参与搜索。
    """
    queue = deque([(container, depth, path)])
    while queue:
        current, current_depth, current_path = queue.popleft()
        yield current, current_depth, current_path
        if current_depth >= MAX_NESTED_DEPTH:
            continue
        for key, value in current.items():
            if key in NON_DATA_LIST_KEYS or not isinstance(value, dict):
                continue
            queue.append((value, current_depth + 1, _join_path(current_path, key)))


def _valid_entity_array(value: list, key: str) -> bool:
    """至少有一个元素能产出非空文本；弱别名不接受字符串元素。"""
    allow_strings = key in STRONG_ENTITY_ARRAY_KEYS
    for item in value:
        if isinstance(item, dict):
            _, text = _first_scalar(item, ENTITY_TEXT_KEYS)
            if text:
                return True
        elif allow_strings and _scalar_text(item):
            return True
    return False


def _valid_relation_array(value: list, key: str) -> bool:
    """至少有一个 dict 元素同时含 from 类与 to 类字段。"""
    return any(
        isinstance(item, dict) and _looks_like_relation(item) for item in value
    )


def _find_nested_array(container: dict, keys: tuple, validator, predicate):
    """两阶段查找嵌套数组。

    第一阶段按「别名优先级 → BFS 深度」收集候选并逐个校验；全部不通过时，
    才退回按结构谓词扫描。返回 (数组, 映射路径) 或 None。
    """
    containers = list(_iter_nested_dicts(container))
    candidates = []
    for priority, key in enumerate(keys):
        for current, current_depth, current_path in containers:
            value = current.get(key)
            if isinstance(value, list) and value:
                candidates.append(
                    (priority, current_depth, key, value, _join_path(current_path, key))
                )
    candidates.sort(key=lambda item: (item[0], item[1]))
    for _, _, key, value, path in candidates:
        if validator(value, key):
            return value, path

    for current, _, current_path in containers:
        for key, value in current.items():
            if key in NON_DATA_LIST_KEYS or not isinstance(value, list) or not value:
                continue
            if all(
                isinstance(item, dict) and predicate(item) for item in value
            ):
                return value, _join_path(current_path, key)
    return None


def _resolve_endpoint(value: str, entity_ids: dict, text_ids: dict) -> str:
    if not value:
        return ""
    if value in entity_ids:
        return entity_ids[value]
    return text_ids.get(value, "")


def _extract_file_name(record: dict, fallback_file_name: str):
    """返回 (文件名, 命中的文件字段键)。"""
    file_key = _first_str_key(record, FILE_NAME_KEYS)
    if not file_key:
        for path_key in ("source_path", "markdown_path"):
            value = record.get(path_key)
            if isinstance(value, str) and value.strip():
                file_key = path_key
                break

    file_name = ""
    if file_key:
        raw_value = _scalar_text(record.get(file_key))
        if raw_value:
            file_name = re.split(r"[\\/]", raw_value)[-1].strip()
    if not file_name:
        file_name = _scalar_text(fallback_file_name) or "未命名文件"
    return file_name, file_key


def _build_endpoint_map(entities: list) -> dict:
    """raw_id → 实体 id，同一 raw_id 首次出现优先。"""
    entity_ids = {}
    for entity in entities:
        raw_id = entity["raw_id"]
        if raw_id and raw_id not in entity_ids:
            entity_ids[raw_id] = entity["id"]
    return entity_ids


def _build_text_map(entities: list) -> dict:
    """实体文本 → 实体 id，同一文本首次出现优先。"""
    text_ids = {}
    for entity in entities:
        text_ids.setdefault(entity["text"], entity["id"])
    return text_ids


def parse_jsonl(
    path: str | Path, fallback_file_name: str = ""
) -> JsonlParseResult:
    """解析 JSONL 文件，返回规范化记录与识别到的字段映射。

    先逐记录提取实体并建立文件级端点映射，再解析关系，
    从而支持实体与关系分行导出的格式。
    """
    text = _read_text(path)
    raw_records, bad_lines, total_lines, warnings = _split_records(text)
    mappings: dict[str, str] = {}
    prepared: list[dict] = []
    file_id_maps: dict[str, dict] = {}
    file_text_maps: dict[str, dict] = {}

    # 第一遍：提取实体，建立记录内与文件级的端点映射
    for record_index, record in enumerate(raw_records):
        file_name, file_key = _extract_file_name(record, fallback_file_name)
        if file_key and "file" not in mappings:
            mappings["file"] = file_key

        raw_entities, entities_path = _extract_entities(record)
        if not raw_entities:
            nested = _find_nested_array(
                record, ENTITY_ARRAY_KEYS, _valid_entity_array, _looks_like_entity
            )
            if nested is not None:
                raw_entities, entities_path = nested
        raw_relations, relations_path = _extract_relations(record)
        if not raw_relations:
            nested = _find_nested_array(
                record,
                RELATION_ARRAY_KEYS,
                _valid_relation_array,
                _looks_like_relation,
            )
            if nested is not None:
                raw_relations, relations_path = nested

        entities = []
        seen_raw_ids: set = set()
        for position, item in enumerate(raw_entities):
            entity = _normalize_entity(
                item, position, record_index, seen_raw_ids, warnings
            )
            if entity is not None:
                entities.append(entity)

        if entities and entities_path and "entities" not in mappings:
            mappings["entities"] = entities_path

        file_ids = file_id_maps.setdefault(file_name, {})
        file_texts = file_text_maps.setdefault(file_name, {})
        for entity in entities:
            raw_id = entity["raw_id"]
            if raw_id:
                file_ids.setdefault(raw_id, entity["id"])
            file_texts.setdefault(entity["text"], entity["id"])

        prepared.append({
            "record_index": record_index,
            "file_name": file_name,
            "entities": entities,
            "raw_relations": raw_relations,
            "relations_path": relations_path,
        })

    # 第二遍：解析关系，先记录内映射，再回退到同文件的其他记录
    records: list[dict] = []
    for item in prepared:
        record_index = item["record_index"]
        file_name = item["file_name"]
        entities = item["entities"]
        entity_ids = _build_endpoint_map(entities)
        text_ids = _build_text_map(entities)
        file_ids = file_id_maps.get(file_name, {})
        file_texts = file_text_maps.get(file_name, {})

        relations = []
        for raw_relation in item["raw_relations"]:
            if not isinstance(raw_relation, dict):
                continue
            from_key, raw_from = _first_scalar(raw_relation, REL_FROM_KEYS)
            to_key, raw_to = _first_scalar(raw_relation, REL_TO_KEYS)
            if not from_key or not to_key:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"第 {record_index + 1} 条记录：关系缺少 from/to 字段，已跳过"
                    )
                continue
            source = _resolve_endpoint(raw_from, entity_ids, text_ids) or (
                _resolve_endpoint(raw_from, file_ids, file_texts)
            )
            target = _resolve_endpoint(raw_to, entity_ids, text_ids) or (
                _resolve_endpoint(raw_to, file_ids, file_texts)
            )
            if not source or not target:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"第 {record_index + 1} 条记录：关系端点无法匹配，已跳过（{raw_from} → {raw_to}）"
                    )
                continue
            _, rel_type = _first_scalar(raw_relation, REL_TYPE_KEYS)
            relations.append({
                "source": source,
                "target": target,
                "type": rel_type,
            })

        relations_path = item["relations_path"]
        if relations and relations_path and "relations" not in mappings:
            mappings["relations"] = relations_path

        records.append({
            "file_name": file_name,
            "entities": entities,
            "relations": relations,
        })

    return JsonlParseResult(
        records=records,
        mappings=mappings,
        warnings=warnings,
        total_lines=total_lines,
        bad_lines=bad_lines,
    )


def _add_edge(edges, seen, source, target, relation, origin):
    """创建一条边并返回；被去重或自环丢弃时返回 None。"""
    if not source or not target or source == target:
        return None
    key = (source, target, relation)
    if key in seen:
        return None
    seen.add(key)
    edge = {
        "id": str(uuid.uuid4()),
        "source": source,
        "target": target,
        "relation": relation,
        "kind": "relation",
        "characteristics": [],
        "weight": 1.0,
        "origin": origin,
    }
    edges.append(edge)
    return edge


def build_graph(records, origin: str = "jsonl", fallback_file_name: str = ""):
    """把规范化记录构建为节点、边与预览汇总。

    节点 name 保留原始文本；HTML 安全显示由渲染层
    （NodeCard.vue / App.vue）负责，避免污染检索与节点合并。
    """
    nodes = []
    edges = []
    file_nodes = {}
    entity_nodes = {}
    entity_id_nodes = {}
    entities_by_file = {}
    file_order = []
    edge_seen = set()
    labels = {}
    relation_edges = []
    unresolved_relations = 0

    # 1. 先创建文件节点，保持首次出现顺序
    for record in records:
        name = record.get("file_name") or fallback_file_name or "未命名文件"
        if name in file_nodes:
            continue
        node = {
            "id": str(uuid.uuid4()),
            "name": name,
            "label": FILE_LABEL,
            "x": 0,
            "y": 0,
            "parent_id": None,
            "attributes": [],
            "origin": origin,
        }
        file_nodes[name] = node
        file_order.append(name)
        nodes.append(node)

    # 2. 创建实体节点（全局合并），并记录每个文件首次创建的新实体
    local_maps = {}
    for record_index, record in enumerate(records):
        file_name = record.get("file_name") or fallback_file_name or "未命名文件"
        file_node = file_nodes[file_name]
        created = entities_by_file.setdefault(file_name, [])
        local_map = {}

        for entity in record.get("entities", []):
            text = entity.get("text", "")
            label = entity.get("label") or DEFAULT_ENTITY_LABEL
            if label == FILE_LABEL:
                # 避免与文件节点同名标签，前端合并时会冲突
                label = DEFAULT_ENTITY_LABEL
            key = (label, text)
            node = entity_nodes.get(key)
            if node is None:
                node = {
                    "id": str(uuid.uuid4()),
                    "name": text,
                    "label": label,
                    "x": 0,
                    "y": 0,
                    "parent_id": None,
                    "attributes": [],
                    "origin": origin,
                }
                entity_nodes[key] = node
                nodes.append(node)
                created.append(node)
                labels[label] = labels.get(label, 0) + 1
            entity_id_nodes[entity["id"]] = node
            local_map[entity["id"]] = node
            _add_edge(
                edges, edge_seen, file_node["id"], node["id"], CONTAIN_RELATION, origin
            )

        local_maps[record_index] = local_map

    # 3. 全部实体创建完成后再处理关系，支持关系行先于实体行
    for record_index, record in enumerate(records):
        local_map = local_maps.get(record_index, {})
        for relation in record.get("relations", []):
            # 跨记录关系：记录内优先，回退到全局已创建的实体
            source = local_map.get(relation["source"]) or entity_id_nodes.get(
                relation["source"]
            )
            target = local_map.get(relation["target"]) or entity_id_nodes.get(
                relation["target"]
            )
            if source is None or target is None:
                unresolved_relations += 1
                continue
            edge = _add_edge(
                edges,
                edge_seen,
                source["id"],
                target["id"],
                relation["type"] or DEFAULT_RELATION,
                origin,
            )
            if edge is not None:
                relation_edges.append(edge)

    # 4. 所有节点创建完成后再定位：文件块纵向堆叠，实体 4 列网格
    cursor_y = 0
    for file_name in file_order:
        file_node = file_nodes[file_name]
        file_node["x"] = 0
        file_node["y"] = cursor_y
        file_entities = entities_by_file.get(file_name, [])
        for index, node in enumerate(file_entities):
            node["x"] = ENTITY_START_X + (index % ENTITY_COLS) * ENTITY_DX
            node["y"] = cursor_y + (index // ENTITY_COLS) * ENTITY_DY
        rows = max(1, math.ceil(len(file_entities) / ENTITY_COLS))
        cursor_y += max(CARD_H, rows * ENTITY_DY) + BLOCK_GAP

    node_names = {node["id"]: node["name"] for node in nodes}
    entity_samples = [n for n in nodes if n["label"] != FILE_LABEL][:10]
    if len(entity_samples) < 10:
        file_samples = [n for n in nodes if n["label"] == FILE_LABEL]
        entity_samples += file_samples[: 10 - len(entity_samples)]

    summary = {
        "records": len(records),
        "files": len(file_nodes),
        "entities": len(entity_nodes),
        "relations": len(relation_edges),
        "unresolved_relations": unresolved_relations,
        "labels": dict(sorted(labels.items(), key=lambda item: item[1], reverse=True)),
        "file_names": list(file_order),
        "sample_nodes": [
            {"name": n["name"], "label": n["label"]} for n in entity_samples
        ],
        "sample_edges": [
            {
                "source": e["source"],
                "source_name": node_names.get(e["source"], ""),
                "target": e["target"],
                "target_name": node_names.get(e["target"], ""),
                "relation": e["relation"],
            }
            for e in relation_edges[:10]
        ],
    }
    return nodes, edges, summary
