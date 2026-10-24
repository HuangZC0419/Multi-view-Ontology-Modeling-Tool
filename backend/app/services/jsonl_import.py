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


@dataclass
class JsonlParseResult:
    """JSONL 解析结果。"""

    records: list = field(default_factory=list)
    mappings: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    total_lines: int = 0
    bad_lines: int = 0


def _read_text(path) -> str:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _first_key(obj: dict, keys: tuple) -> str:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return key
    return ""


def _first_str_key(obj: dict, keys: tuple) -> str:
    """只接受非空字符串值，避免把嵌套对象误当成文件名。"""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return key
    return ""


def _split_records(text: str):
    """返回 (records, bad_lines, total_lines, warnings)。"""
    warnings = []
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            records = [item for item in data if isinstance(item, dict)]
            bad = len(data) - len(records)
            if bad:
                warnings.append(f"JSON 数组中有 {bad} 个元素不是对象，已跳过")
            return records, bad, len(data), warnings

    records = []
    bad = 0
    total = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        brace = line.find("{")
        candidate = line[brace:] if brace >= 0 else line
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
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
    return records, bad, total, warnings


def _normalize_entity(item: Any, position: int, record_index: int):
    if isinstance(item, str):
        text = item.strip()
        label = DEFAULT_ENTITY_LABEL
        raw_id = ""
    elif isinstance(item, dict):
        text_key = _first_key(item, ENTITY_TEXT_KEYS)
        text = str(item.get(text_key, "")).strip() if text_key else ""
        label_key = _first_key(item, ENTITY_LABEL_KEYS)
        label = str(item.get(label_key, "")).strip() if label_key else ""
        id_key = _first_key(item, ENTITY_ID_KEYS)
        raw_id = str(item.get(id_key, "")).strip() if id_key else ""
    else:
        return None
    if not text:
        return None
    unique_id = f"{record_index}:{raw_id}" if raw_id else f"{record_index}:#{position}"
    return {
        "id": unique_id,
        "raw_id": raw_id,
        "text": text,
        "label": label or DEFAULT_ENTITY_LABEL,
    }


def _extract_entities(record: dict):
    array_key = ""
    raw_items = []
    fallback_key = ""
    for key in ENTITY_ARRAY_KEYS:
        value = record.get(key)
        if not isinstance(value, list):
            continue
        if not fallback_key:
            fallback_key = key
        if value:
            array_key, raw_items = key, value
            break
    if not array_key and fallback_key:
        array_key = fallback_key
    return raw_items, array_key


def _extract_relations(record: dict):
    array_key = ""
    raw_items = []
    fallback_key = ""
    for key in RELATION_ARRAY_KEYS:
        value = record.get(key)
        if not isinstance(value, list):
            continue
        if not fallback_key:
            fallback_key = key
        if value:
            array_key, raw_items = key, value
            break
    if not array_key and fallback_key:
        array_key = fallback_key
    return raw_items, array_key


def _resolve_endpoint(value: str, entity_ids: dict, text_ids: dict) -> str:
    if not value:
        return ""
    if value in entity_ids:
        return entity_ids[value]
    return text_ids.get(value, "")


def parse_jsonl(path, fallback_file_name: str = "") -> JsonlParseResult:
    """解析 JSONL 文件，返回规范化记录与识别到的字段映射。"""
    text = _read_text(path)
    raw_records, bad_lines, total_lines, warnings = _split_records(text)
    mappings = {}
    records = []

    for record_index, record in enumerate(raw_records):
        file_key = _first_str_key(record, FILE_NAME_KEYS)
        if file_key and "file" not in mappings:
            mappings["file"] = file_key
        if not file_key:
            for path_key in ("source_path", "markdown_path"):
                value = record.get(path_key)
                if isinstance(value, str) and value.strip():
                    file_key = path_key
                    break

        file_name = ""
        if file_key:
            raw_value = record.get(file_key)
            if isinstance(raw_value, str):
                file_name = re.split(r"[\\/]", raw_value.strip())[-1]
        if not file_name:
            file_name = fallback_file_name or "未命名文件"

        raw_entities, entities_key = _extract_entities(record)
        if entities_key and "entities" not in mappings:
            mappings["entities"] = entities_key
        raw_relations, relations_key = _extract_relations(record)
        if relations_key and "relations" not in mappings:
            mappings["relations"] = relations_key

        entities = []
        for position, item in enumerate(raw_entities):
            entity = _normalize_entity(item, position, record_index)
            if entity is not None:
                entities.append(entity)

        entity_ids = {e["raw_id"]: e["id"] for e in entities if e["raw_id"]}
        text_ids = {}
        for entity in entities:
            text_ids.setdefault(entity["text"], entity["id"])

        relations = []
        for item in raw_relations:
            if not isinstance(item, dict):
                continue
            from_key = _first_key(item, REL_FROM_KEYS)
            to_key = _first_key(item, REL_TO_KEYS)
            type_key = _first_key(item, REL_TYPE_KEYS)
            if not from_key or not to_key:
                continue
            raw_from = str(item.get(from_key, "")).strip()
            raw_to = str(item.get(to_key, "")).strip()
            source = _resolve_endpoint(raw_from, entity_ids, text_ids)
            target = _resolve_endpoint(raw_to, entity_ids, text_ids)
            if not source or not target:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"第 {record_index + 1} 条记录：关系端点无法匹配，已跳过（{raw_from} → {raw_to}）"
                    )
                continue
            relations.append({
                "source": source,
                "target": target,
                "type": str(item.get(type_key, "")).strip() if type_key else "",
            })

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
