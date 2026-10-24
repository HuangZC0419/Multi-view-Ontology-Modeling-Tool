"""通用 JSONL 标注数据解析与知识图谱构建。

兼容：字段别名、数字/字符串 id、行首脏前缀、同文件多行、
整文件 JSON 数组、id 或实体文本作为关系端点。
"""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FILE_LABEL = "文件"
DEFAULT_ENTITY_LABEL = "实体"
DEFAULT_RELATION = "关联"
CONTAIN_RELATION = "包含"

FILE_NAME_KEYS = (
    "file_name", "fileName", "filename", "document_name", "doc_name",
    "source_file", "file", "文件名", "文档名", "文件",
)
ENTITY_ARRAY_KEYS = (
    "spans", "entities", "mentions", "ner", "实体", "标注片段", "labels", "annotations",
)
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
    if total and bad == total:
        warnings.append("所有非空行均解析失败，疑似编码不匹配")
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
    """仅接受非空数组，空数组视为不存在以便后续别名或嵌套兜底。"""
    for key in ENTITY_ARRAY_KEYS:
        value = record.get(key)
        if isinstance(value, list) and value:
            return value, key
    return [], ""


def _extract_relations(record: dict):
    """仅接受非空数组，空数组视为不存在以便后续别名或嵌套兜底。"""
    for key in RELATION_ARRAY_KEYS:
        value = record.get(key)
        if isinstance(value, list) and value:
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


def _find_nested_list(container: dict, predicate, depth: int = 1, path: str = ""):
    """在记录内最多递归 MAX_NESTED_DEPTH 层查找符合结构的数组。"""
    for key, value in container.items():
        child_path = f"{path}.{key}" if path else key
        if isinstance(value, list):
            if key in NON_DATA_LIST_KEYS:
                continue
            if value and all(
                isinstance(item, dict) and predicate(item) for item in value
            ):
                return value, child_path
        elif isinstance(value, dict) and depth < MAX_NESTED_DEPTH:
            found = _find_nested_list(value, predicate, depth + 1, child_path)
            if found is not None:
                return found
    return None


def _resolve_endpoint(value: str, entity_ids: dict, text_ids: dict) -> str:
    if not value:
        return ""
    if value in entity_ids:
        return entity_ids[value]
    return text_ids.get(value, "")


def parse_jsonl(
    path: str | Path, fallback_file_name: str = ""
) -> JsonlParseResult:
    """解析 JSONL 文件，返回规范化记录与识别到的字段映射。"""
    text = _read_text(path)
    raw_records, bad_lines, total_lines, warnings = _split_records(text)
    mappings: dict[str, str] = {}
    records: list[dict] = []

    for record_index, record in enumerate(raw_records):
        file_key = _first_str_key(record, FILE_NAME_KEYS)
        if not file_key:
            for path_key in ("source_path", "markdown_path"):
                value = record.get(path_key)
                if isinstance(value, str) and value.strip():
                    file_key = path_key
                    break
        if file_key and "file" not in mappings:
            mappings["file"] = file_key

        file_name = ""
        if file_key:
            raw_value = _scalar_text(record.get(file_key))
            if raw_value:
                file_name = re.split(r"[\\/]", raw_value)[-1].strip()
        if not file_name:
            file_name = _scalar_text(fallback_file_name) or "未命名文件"

        raw_entities, entities_path = _extract_entities(record)
        if not raw_entities:
            nested = _find_nested_list(record, _looks_like_entity)
            if nested is not None:
                raw_entities, entities_path = nested
        raw_relations, relations_path = _extract_relations(record)
        if not raw_relations:
            nested = _find_nested_list(record, _looks_like_relation)
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

        entity_ids = {}
        for entity in entities:
            raw_id = entity["raw_id"]
            if raw_id and raw_id not in entity_ids:
                entity_ids[raw_id] = entity["id"]
        text_ids = {}
        for entity in entities:
            text_ids.setdefault(entity["text"], entity["id"])

        relations = []
        for item in raw_relations:
            if not isinstance(item, dict):
                continue
            from_key, raw_from = _first_scalar(item, REL_FROM_KEYS)
            to_key, raw_to = _first_scalar(item, REL_TO_KEYS)
            if not from_key or not to_key:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"第 {record_index + 1} 条记录：关系缺少 from/to 字段，已跳过"
                    )
                continue
            source = _resolve_endpoint(raw_from, entity_ids, text_ids)
            target = _resolve_endpoint(raw_to, entity_ids, text_ids)
            if not source or not target:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"第 {record_index + 1} 条记录：关系端点无法匹配，已跳过（{raw_from} → {raw_to}）"
                    )
                continue
            _, rel_type = _first_scalar(item, REL_TYPE_KEYS)
            relations.append({
                "source": source,
                "target": target,
                "type": rel_type,
            })

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
