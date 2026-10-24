# Excel 导入修复 + JSONL 知识图谱导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复数据源面板被浮层联动卸载导致的 Excel 导入失效，并新增兼容多种格式的 JSONL 标注导入，把文件、实体与关系组织成知识图谱。

**Architecture:** 后端新增独立的 `jsonl_import` 服务（字段别名探测 + 容错行解析 + 全局合并 + 确定性布局），通过两个 API 暴露预览与导入；前端复用上传入口，新增 JSONL 预览组件，并在追加到画布时按 `(label, name)` 合并节点、重映射边 id；Excel 修复只改浮层关闭条件。

**Tech Stack:** FastAPI + Pydantic + openpyxl（Python 3.8，`benti-py38` 环境）、Vue 3 + Vite、标准库 `unittest`

---

## 文件结构

| 文件 | 操作 | 职责 |
|---|---|---|
| `backend/app/services/jsonl_import.py` | 新建 | JSONL 容错解析、图构建、布局、汇总 |
| `backend/tests/__init__.py` | 新建 | 测试包标记 |
| `backend/tests/test_jsonl_import.py` | 新建 | 解析与图构建单元测试 |
| `backend/app/models.py` | 修改 | 新增 `JsonlImportSelection` |
| `backend/app/main.py` | 修改 | `OntologyNode` 增加 `label` |
| `backend/app/routers/knowledge.py` | 修改 | `ConceptMatch` 增加 `label` 并填充 |
| `backend/app/routers/datasource.py` | 修改 | 文件名解码、JSONL 上传/导入接口 |
| `backend/app/connectors/file_parser.py` | 修改 | Excel 异常信息不再被吞掉 |
| `frontend/src/App.vue` | 修改 | 浮层豁免、JSONL 合并逻辑 |
| `frontend/src/components/datasource/FileUploader.vue` | 修改 | 接受 `.jsonl` 并传递摘要 |
| `frontend/src/components/datasource/DataSourcePanel.vue` | 修改 | 按来源类型选择预览组件 |
| `frontend/src/components/datasource/JsonlImportPreview.vue` | 新建 | JSONL 预览与确认导入 |
| `frontend/src/components/canvas/NodeCard.vue` | 修改 | 显示节点标签 |
| `backend/scripts/smoke_jsonl_import.py` | 新建 | 真实 HTTP 冒烟脚本 |

---

## Task 1: JSONL 容错解析层

**Files:**
- Create: `backend/app/services/jsonl_import.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_jsonl_import.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/__init__.py`（空文件）。

创建 `backend/tests/test_jsonl_import.py`：

```python
import json
import os
import tempfile
import unittest

from app.services.jsonl_import import parse_jsonl


SAMPLE_A = (
    '0{"file_name":"test.pdf","text":"2025 年个人酬金查询\\n2025 年税后实发金额33160元",'
    '"spans":[{"id":1,"start":25,"end":31,"label":"参数","text":"33160元"},'
    '{"id":2,"start":13,"end":19,"label":"参数","text":"2025 年"}],'
    '"relations":[{"fromId":2,"toId":1,"type":"属于"}]}\n'
    '{"file_name":"GBT+4423-2020.pdf","text":"标准正文",'
    '"spans":[{"id":1,"label":"关键工序","text":"冷拉"}],"relations":[]}\n'
)


def write_temp(text, suffix=".jsonl", encoding="utf-8"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "w", encoding=encoding) as fh:
        fh.write(text)
    return path


class ParseJsonlTests(unittest.TestCase):
    def test_tolerates_leading_garbage_prefix(self):
        result = parse_jsonl(write_temp(SAMPLE_A))
        self.assertEqual(result.bad_lines, 0)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.mappings["file"], "file_name")
        self.assertEqual(result.mappings["entities"], "spans")
        self.assertEqual(result.mappings["relations"], "relations")

    def test_relation_resolves_by_numeric_id(self):
        result = parse_jsonl(write_temp(SAMPLE_A))
        relation = result.records[0]["relations"][0]
        self.assertEqual(relation["type"], "属于")
        self.assertNotEqual(relation["source"], relation["target"])

    def test_multi_line_same_file_is_kept_as_records(self):
        text = "".join(
            json.dumps(
                {
                    "file_name": "a.png",
                    "spans": [{"id": f"s{i}", "label": "x", "text": "甲"}],
                },
                ensure_ascii=False,
            )
            + "\n"
            for i in range(3)
        )
        result = parse_jsonl(write_temp(text))
        self.assertEqual(len(result.records), 3)

    def test_bad_line_is_counted(self):
        result = parse_jsonl(write_temp('{"file_name":"a.png","spans":[]}\nnot json\n'))
        self.assertEqual(result.bad_lines, 1)
        self.assertEqual(len(result.records), 1)

    def test_json_array_file(self):
        text = json.dumps(
            [{"file_name": "a.png", "spans": [{"text": "甲", "label": "x"}]}],
            ensure_ascii=False,
        )
        result = parse_jsonl(write_temp(text))
        self.assertEqual(len(result.records), 1)

    def test_relation_endpoint_by_entity_text(self):
        record = {
            "file_name": "a.png",
            "entities": [
                {"text": "甲", "label": "x"},
                {"text": "乙", "label": "x"},
            ],
            "relations": [{"from": "甲", "to": "乙", "type": "关联"}],
        }
        result = parse_jsonl(write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual(len(result.records[0]["relations"]), 1)

    def test_gbk_encoding(self):
        path = write_temp(
            json.dumps({"file_name": "标准.pdf", "spans": [{"text": "甲", "label": "x"}]}, ensure_ascii=False),
            encoding="gb18030",
        )
        result = parse_jsonl(path)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["file_name"], "标准.pdf")

    def test_annotations_used_only_without_spans(self):
        with_spans = {
            "file_name": "a.png",
            "spans": [{"id": "s1", "text": "甲", "label": "x"}],
            "annotations": [{"id": "a1", "label": "汇总"}],
        }
        result = parse_jsonl(write_temp(json.dumps(with_spans, ensure_ascii=False)))
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["甲"])

        no_spans = {
            "file_name": "a.png",
            "annotations": [{"text": "乙", "label": "汇总"}],
        }
        result = parse_jsonl(write_temp(json.dumps(no_spans, ensure_ascii=False)))
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["乙"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe -m unittest tests.test_jsonl_import -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.jsonl_import'`

- [ ] **Step 3: 实现解析层**

创建 `backend/app/services/jsonl_import.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe -m unittest tests.test_jsonl_import -v
```
Expected: 8 tests, `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/jsonl_import.py backend/tests/__init__.py backend/tests/test_jsonl_import.py
git commit -m "feat(backend): 新增容错 JSONL 解析层"
```

---

## Task 2: 图构建、全局合并与布局

**Files:**
- Modify: `backend/app/services/jsonl_import.py`
- Test: `backend/tests/test_jsonl_import.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_jsonl_import.py` 顶部导入处改为：

```python
from app.services.jsonl_import import build_graph, parse_jsonl
```

在文件末尾（`if __name__ == "__main__":` 之前）追加：

```python
class BuildGraphTests(unittest.TestCase):
    def test_global_merge_across_files(self):
        text = (
            '{"file_name":"a.pdf","spans":[{"id":"1","label":"参数","text":"2025 年"}]}\n'
            '{"file_name":"b.pdf","spans":[{"id":"1","label":"参数","text":"2025 年"}]}\n'
        )
        nodes, edges, summary = build_graph(parse_jsonl(write_temp(text)).records, origin="jsonl:test")
        self.assertEqual(summary["files"], 2)
        self.assertEqual(summary["entities"], 1)
        containment = [e for e in edges if e["relation"] == "包含"]
        self.assertEqual(len(containment), 2)

    def test_same_text_different_label_is_separate(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"参数","text":"甲"},'
            '{"id":"2","label":"工序","text":"甲"}]}\n'
        )
        _, _, summary = build_graph(parse_jsonl(write_temp(text)).records)
        self.assertEqual(summary["entities"], 2)

    def test_duplicate_relation_is_deduped(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},{"id":"2","label":"x","text":"乙"}],'
            '"relations":[{"fromId":"1","toId":"2","type":"关联"},'
            '{"fromId":"1","toId":"2","type":"关联"}]}\n'
        )
        _, edges, summary = build_graph(parse_jsonl(write_temp(text)).records)
        relations = [e for e in edges if e["relation"] == "关联"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(summary["relations"], 1)

    def test_positions_are_deterministic_and_unique(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},{"id":"2","label":"x","text":"乙"}]}\n'
        )
        nodes1, _, _ = build_graph(parse_jsonl(write_temp(text)).records)
        nodes2, _, _ = build_graph(parse_jsonl(write_temp(text)).records)
        positions1 = sorted((round(n["x"], 3), round(n["y"], 3)) for n in nodes1)
        positions2 = sorted((round(n["x"], 3), round(n["y"], 3)) for n in nodes2)
        self.assertEqual(positions1, positions2)
        self.assertEqual(len({(n["x"], n["y"]) for n in nodes1}), len(nodes1))

    def test_entity_text_is_html_escaped(self):
        text = '{"file_name":"a.pdf","spans":[{"id":"1","label":"x","text":"<b>&"}]}\n'
        nodes, _, _ = build_graph(parse_jsonl(write_temp(text)).records)
        self.assertIn("&lt;b&gt;&amp;", {n["name"] for n in nodes})

    def test_file_label_and_origin(self):
        text = '{"file_name":"a.pdf","spans":[]}\n'
        nodes, _, _ = build_graph(parse_jsonl(write_temp(text)).records, origin="jsonl:x.jsonl")
        self.assertEqual(nodes[0]["label"], "文件")
        self.assertEqual(nodes[0]["origin"], "jsonl:x.jsonl")
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe -m unittest tests.test_jsonl_import.BuildGraphTests -v
```
Expected: `ImportError: cannot import name 'build_graph'`

- [ ] **Step 3: 实现图构建**

在 `backend/app/services/jsonl_import.py` 末尾追加：

```python
def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ring_offset(ordinal: int):
    """按序号返回环形偏移：第一环 8 个（半径 170），之后每环 12 个（半径 +90）。"""
    ring = 0
    remaining = ordinal
    capacity = 8
    while remaining >= capacity:
        remaining -= capacity
        ring += 1
        capacity = 12
    radius = 170 + ring * 90
    angle = 2 * math.pi * remaining / capacity
    return radius * math.cos(angle), radius * math.sin(angle)


def _add_edge(edges, seen, source, target, relation, origin):
    if not source or not target or source == target:
        return
    key = (source, target, relation)
    if key in seen:
        return
    seen.add(key)
    edges.append({
        "id": str(uuid.uuid4()),
        "source": source,
        "target": target,
        "relation": relation,
        "kind": "relation",
        "characteristics": [],
        "weight": 1.0,
        "origin": origin,
    })


def build_graph(records, origin: str = "jsonl", fallback_file_name: str = ""):
    """把规范化记录构建为节点、边与预览汇总。"""
    nodes = []
    edges = []
    file_nodes = {}
    entity_nodes = {}
    entity_ordinal = {}
    edge_seen = set()
    labels = {}

    for record in records:
        name = record.get("file_name") or fallback_file_name or "未命名文件"
        if name in file_nodes:
            continue
        index = len(file_nodes)
        node = {
            "id": str(uuid.uuid4()),
            "name": _escape_html(name),
            "label": FILE_LABEL,
            "x": (index % 3) * 420,
            "y": (index // 3) * 360,
            "parent_id": None,
            "attributes": [],
            "origin": origin,
        }
        file_nodes[name] = node
        nodes.append(node)

    for record in records:
        file_name = record.get("file_name") or fallback_file_name or "未命名文件"
        file_node = file_nodes[file_name]
        local_map = {}

        for entity in record.get("entities", []):
            text = entity.get("text", "")
            label = entity.get("label") or DEFAULT_ENTITY_LABEL
            key = (label, text)
            node = entity_nodes.get(key)
            if node is None:
                ordinal = entity_ordinal.get(file_name, 0)
                dx, dy = _ring_offset(ordinal)
                entity_ordinal[file_name] = ordinal + 1
                node = {
                    "id": str(uuid.uuid4()),
                    "name": _escape_html(text),
                    "label": label,
                    "x": file_node["x"] + 100 + dx,
                    "y": file_node["y"] + 35 + dy,
                    "parent_id": None,
                    "attributes": [],
                    "origin": origin,
                }
                entity_nodes[key] = node
                nodes.append(node)
                labels[label] = labels.get(label, 0) + 1
            local_map[entity["id"]] = node
            _add_edge(edges, edge_seen, file_node["id"], node["id"], CONTAIN_RELATION, origin)

        for relation in record.get("relations", []):
            source = local_map.get(relation["source"])
            target = local_map.get(relation["target"])
            if source is None or target is None:
                continue
            _add_edge(
                edges,
                edge_seen,
                source["id"],
                target["id"],
                relation["type"] or DEFAULT_RELATION,
                origin,
            )

    relation_edges = [e for e in edges if e["relation"] != CONTAIN_RELATION]
    sample_edges = relation_edges[:10] or edges[:10]
    summary = {
        "records": len(records),
        "files": len(file_nodes),
        "entities": len(entity_nodes),
        "relations": len(relation_edges),
        "labels": dict(sorted(labels.items(), key=lambda item: item[1], reverse=True)),
        "file_names": list(file_nodes.keys()),
        "sample_nodes": [{"name": n["name"], "label": n["label"]} for n in nodes[:10]],
        "sample_edges": [
            {"source": e["source"], "target": e["target"], "relation": e["relation"]}
            for e in sample_edges
        ],
    }
    return nodes, edges, summary
```

- [ ] **Step 4: 运行全部测试确认通过**

Run:
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe -m unittest tests.test_jsonl_import -v
```
Expected: 14 tests, `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/jsonl_import.py backend/tests/test_jsonl_import.py
git commit -m "feat(backend): JSONL 图构建、全局合并与确定性布局"
```

---

## Task 3: 后端模型与 API

**Files:**
- Modify: `backend/app/main.py:41-48`
- Modify: `backend/app/models.py`
- Modify: `backend/app/routers/knowledge.py:18-27`
- Modify: `backend/app/routers/datasource.py:1-30`、`127-160`、文件末尾
- Modify: `backend/app/connectors/file_parser.py:64-75`

- [ ] **Step 1: 给节点模型加 label**

`backend/app/main.py` 的 `OntologyNode` 增加一行（放在 `name` 之后）：

```python
class OntologyNode(BaseModel):
    id: str
    name: str = Field(min_length=1)
    label: str = ""
    x: float
    y: float
    parent_id: str | None = None
    attributes: list[dict[str, str]] = Field(default_factory=list)
    origin: str = "manual"
```

- [ ] **Step 2: 增加导入请求模型**

`backend/app/models.py` 末尾追加：

```python
class JsonlImportSelection(BaseModel):
    """JSONL 导入请求"""
    source_id: str
```

- [ ] **Step 3: 检索结果携带 label**

`backend/app/routers/knowledge.py` 的 `ConceptMatch` 增加：

```python
    label: str = ""
```

在 `search_knowledge` 构造 `ConceptMatch(...)` 时增加参数：

```python
                label=node.label or "",
```

- [ ] **Step 4: 修改数据源路由**

`backend/app/routers/datasource.py` 顶部导入改为：

```python
import json
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models import ImportSelection, JsonlImportSelection
from app.connectors.dameng import SimDamengConnector, DamengConnector
from app.connectors.file_parser import FileParserConnector
from app.services.jsonl_import import build_graph, parse_jsonl
from app.services.ontology_extract import extract_ontology_nodes, extract_ontology_from_data
```

在 `_load_upload_meta` 之后加入：

```python
ALLOWED_FILE_EXTS = (".xlsx", ".xls", ".csv", ".jsonl")
_FILE_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")


def _decode_upload_filename(name: str) -> str:
    """修复 multipart 文件名被按 latin-1 解码导致的中文乱码。"""
    if not name:
        return name
    try:
        fixed = name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name
    return fixed
```

把 `upload_file` 整体替换为：

```python
@router.post("/file/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 Excel/CSV/JSONL 文件，返回解析后的结构"""
    _ensure_upload_dir()

    original_name = _decode_upload_filename(file.filename or "")
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_FILE_EXTS:
        raise HTTPException(400, f"不支持的文件格式: {ext}，仅支持 .xlsx .xls .csv .jsonl")

    file_id = str(uuid.uuid4())
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    _save_upload_meta(file_id, original_name or save_name, ext)

    if ext == ".jsonl":
        result = parse_jsonl(save_path, fallback_file_name=original_name)
        _, _, summary = build_graph(
            result.records,
            origin=f"jsonl:{original_name or save_name}",
            fallback_file_name=original_name,
        )
        summary["mappings"] = result.mappings
        summary["warnings"] = result.warnings
        summary["bad_lines"] = result.bad_lines
        summary["records"] = len(result.records)
        return {
            "file_id": file_id,
            "file_name": original_name,
            "file_type": ext,
            "jsonl_summary": summary,
        }

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
        "file_name": original_name,
        "file_type": ext,
        "tables": [t.model_dump() for t in tables],
        "columns": columns_map,
    }
```

在文件末尾追加导入接口：

```python
# ============================================================
# JSONL 标注导入
# ============================================================

@router.post("/jsonl/import")
async def import_jsonl(payload: JsonlImportSelection):
    """把 JSONL 标注文件转换为文件节点、实体节点与关系边"""
    _ensure_upload_dir()
    if not _FILE_ID_PATTERN.match(payload.source_id):
        raise HTTPException(400, "非法的文件标识")

    path = UPLOAD_DIR / f"{payload.source_id}.jsonl"
    if not path.exists():
        raise HTTPException(404, "文件不存在或已过期")

    meta = _load_upload_meta(payload.source_id)
    original_name = meta.get("file_name", "") or path.name
    result = parse_jsonl(path, fallback_file_name=original_name)
    nodes, edges, summary = build_graph(
        result.records,
        origin=f"jsonl:{original_name}",
        fallback_file_name=original_name,
    )
    if not nodes:
        raise HTTPException(400, "未识别到有效记录，请检查 JSONL 格式")

    summary["mappings"] = result.mappings
    summary["warnings"] = result.warnings
    summary["bad_lines"] = result.bad_lines
    summary["records"] = len(result.records)
    return {"nodes": nodes, "edges": edges, "summary": summary}
```

- [ ] **Step 5: 让 Excel 异常可诊断**

`backend/app/connectors/file_parser.py` 的 `_parse_excel` 整体替换为：

```python
    async def _parse_excel(self) -> bool:
        errors = []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(self._file_path, read_only=True, data_only=True)
            try:
                return await self._parse_openpyxl(wb)
            finally:
                wb.close()
        except Exception as exc:
            errors.append(f"openpyxl: {exc}")

        try:
            import xlrd
            wb = xlrd.open_workbook(self._file_path)
            return await self._parse_xlrd(wb)
        except Exception as exc:
            errors.append(f"xlrd: {exc}")

        raise RuntimeError("无法打开 Excel 文件：" + "；".join(errors))
```

- [ ] **Step 6: 验证后端可导入**

Run:
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe -c "from app.main import app; print('routes ok')"
E:/Anaconda/envs/benti-py38/python.exe -m unittest tests.test_jsonl_import -v
```
Expected: 输出 `routes ok`；测试 `OK`

- [ ] **Step 7: 提交**

```bash
git add backend/app/main.py backend/app/models.py backend/app/routers/knowledge.py backend/app/routers/datasource.py backend/app/connectors/file_parser.py
git commit -m "feat(backend): 节点 label 字段与 JSONL 上传/导入接口"
```

---

## Task 4: 修复 Excel 导入被浮层卸载

**Files:**
- Modify: `frontend/src/App.vue:1432-1437`

- [ ] **Step 1: 修改浮层关闭条件**

把 `onFlyoutBodyClick` 替换为：

```js
function onFlyoutBodyClick(event) {
  const btn = event.target.closest("button");
  if (!btn) return;
  // 检索面板的“开始检索”需保留浮层，否则结果会随之消失
  if (btn.classList.contains("ksp-btn")) return;
  // 数据源与 OCR 面板内部按钮会打开弹窗，收起浮层会把弹窗一起卸载
  if (btn.closest(".datasource-panel, .ocr-import-group")) return;
  flyoutOpen.value = false;
}
```

- [ ] **Step 2: 构建验证**

Run:
```bash
cd frontend
npm run build
```
Expected: 构建成功，无语法错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/App.vue
git commit -m "fix(frontend): 数据源面板点击不再关闭浮层，修复 Excel 导入弹窗被卸载"
```

---

## Task 5: JSONL 上传与导入预览

**Files:**
- Modify: `frontend/src/components/datasource/FileUploader.vue:19`、`60-73`、`96-111`、`190`
- Create: `frontend/src/components/datasource/JsonlImportPreview.vue`
- Modify: `frontend/src/components/datasource/DataSourcePanel.vue`

- [ ] **Step 1: 上传器接受 .jsonl**

`FileUploader.vue` 第 19 行改为：

```js
const ACCEPTED_TYPES = ".xlsx,.xls,.csv,.jsonl";
const ALLOWED_EXTENSIONS = [".xlsx", ".xls", ".csv", ".jsonl"];
```

`handleFile` 中的校验替换为：

```js
function handleFile(file) {
  const name = file.name.toLowerCase();
  const ext = name.substring(name.lastIndexOf("."));

  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    errorMessage.value = `不支持的文件格式: ${ext}，仅支持 .xlsx .xls .csv .jsonl`;
    uploadStatus.value = "error";
    return;
  }

  selectedFile.value = file;
  errorMessage.value = "";
  uploadFile(file);
}
```

`uploadFile` 中 `const data = await resp.json();` 之后替换为：

```js
    const data = await resp.json();

    uploadStatus.value = "done";

    if (data.file_type === ".jsonl") {
      const summary = data.jsonl_summary || {};
      statusMessage.value = `解析完成：${data.file_name}（${summary.files || 0} 个文件 / ${summary.entities || 0} 个实体）`;
      emit("preview-ready", {
        source_id: data.file_id,
        sourceType: "jsonl",
        sourceName: data.file_name,
        summary,
        tables: [],
        columns: {},
      });
      return;
    }

    statusMessage.value = `解析完成：${data.file_name}`;

    // 构建 columns 映射 {tableName: [columns]}
    const columnsMap = data.columns || {};
    const tablesList = data.tables || [];

    emit("preview-ready", {
      source_id: data.file_id,
      tables: tablesList,
      columns: columnsMap,
      sourceType: "file",
      sourceName: data.file_name,
    });
```

模板中的提示文案改为：

```html
              <p class="fu-drop-hint">支持 Excel (.xlsx / .xls)、CSV (.csv) 与 JSONL (.jsonl)</p>
```

- [ ] **Step 2: 新建预览组件**

创建 `frontend/src/components/datasource/JsonlImportPreview.vue`：

```vue
<script setup>
import { computed, ref } from "vue";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const props = defineProps({
  previewData: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["import-done", "back"]);

const summary = computed(() => props.previewData.summary || {});
const mappings = computed(() => summary.value.mappings || {});
const labels = computed(() => Object.entries(summary.value.labels || {}));
const fileNames = computed(() => summary.value.file_names || []);
const warnings = computed(() => summary.value.warnings || []);
const isImporting = ref(false);
const errorMessage = ref("");

const hasContent = computed(
  () => (summary.value.files || 0) > 0 && (summary.value.entities || 0) > 0
);

function mappingText(key, fallback) {
  return mappings.value[key] || fallback;
}

async function confirmImport() {
  if (!hasContent.value || isImporting.value) return;
  isImporting.value = true;
  errorMessage.value = "";
  try {
    const resp = await fetch(`${API_BASE}/api/datasource/jsonl/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_id: props.previewData.source_id }),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || errData.message || "导入失败");
    }
    const data = await resp.json();
    if (!data.nodes || data.nodes.length === 0) {
      throw new Error("未解析到可导入的知识节点");
    }
    emit("import-done", data.nodes, data.edges || [], [], [], { merge: true });
  } catch (err) {
    errorMessage.value = err.message || "导入请求失败";
  } finally {
    isImporting.value = false;
  }
}
</script>

<template>
  <div class="jp-overlay" @click.self="emit('back')">
    <div class="jp-dialog" @click.stop>
      <div class="jp-header">
        <div class="jp-header-left">
          <button class="jp-back" @click="emit('back')">‹</button>
          <h2>JSONL 导入预览</h2>
          <span class="jp-source">{{ previewData.sourceName }}</span>
        </div>
        <button class="jp-close" @click="emit('back')">×</button>
      </div>

      <div class="jp-body">
        <div v-if="errorMessage" class="jp-error">{{ errorMessage }}</div>

        <div class="jp-section">
          <div class="jp-section-title">识别到的字段</div>
          <div class="jp-mapping-row">
            <span>文件名</span><code>{{ mappingText("file", "未识别（使用上传文件名）") }}</code>
          </div>
          <div class="jp-mapping-row">
            <span>实体</span><code>{{ mappingText("entities", "未识别") }}</code>
          </div>
          <div class="jp-mapping-row">
            <span>关系</span><code>{{ mappingText("relations", "未识别") }}</code>
          </div>
        </div>

        <div class="jp-stats">
          <div class="jp-stat"><strong>{{ summary.records || 0 }}</strong><span>记录</span></div>
          <div class="jp-stat"><strong>{{ summary.files || 0 }}</strong><span>文件</span></div>
          <div class="jp-stat"><strong>{{ summary.entities || 0 }}</strong><span>实体</span></div>
          <div class="jp-stat"><strong>{{ summary.relations || 0 }}</strong><span>关系</span></div>
        </div>

        <div class="jp-section" v-if="labels.length">
          <div class="jp-section-title">标签分布</div>
          <div class="jp-label-list">
            <span v-for="[name, count] in labels" :key="name" class="jp-label-chip">
              {{ name }} <b>{{ count }}</b>
            </span>
          </div>
        </div>

        <div class="jp-section" v-if="fileNames.length">
          <div class="jp-section-title">文件（前 20 个）</div>
          <ul class="jp-file-list">
            <li v-for="name in fileNames.slice(0, 20)" :key="name">{{ name }}</li>
          </ul>
        </div>

        <div class="jp-section" v-if="warnings.length">
          <div class="jp-section-title">警告（前 20 条）</div>
          <ul class="jp-warning-list">
            <li v-for="(item, index) in warnings.slice(0, 20)" :key="index">{{ item }}</li>
          </ul>
        </div>

        <div class="jp-empty" v-if="!hasContent">未识别到有效记录，请检查文件格式。</div>
      </div>

      <div class="jp-footer">
        <button class="jp-btn jp-btn-ghost" @click="emit('back')">返回</button>
        <button
          class="jp-btn jp-btn-primary"
          :disabled="isImporting || !hasContent"
          @click="confirmImport"
        >
          {{ isImporting ? "导入中..." : `确认导入（${summary.entities || 0} 实体 / ${summary.relations || 0} 关系）` }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.jp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 152;
}

.jp-dialog {
  width: 640px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 20px 40px -8px rgba(0, 0, 0, 0.16);
}

.jp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.jp-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.jp-header-left h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.jp-source {
  font-size: 12.5px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jp-back,
.jp-close {
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  border-radius: 8px;
  width: 30px;
  height: 30px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.jp-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 20px;
}

.jp-error {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 13px;
}

.jp-section {
  margin-bottom: 16px;
}

.jp-section-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.03em;
}

.jp-mapping-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  font-size: 13px;
  color: #334155;
}

.jp-mapping-row code {
  color: #1d4ed8;
  background: #eff6ff;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
}

.jp-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.jp-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.jp-stat strong {
  font-size: 20px;
  color: #1d4ed8;
}

.jp-stat span {
  font-size: 12px;
  color: #64748b;
}

.jp-label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.jp-label-chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
}

.jp-label-chip b {
  margin-left: 4px;
  color: #1e40af;
}

.jp-file-list,
.jp-warning-list {
  margin: 0;
  padding-left: 18px;
  max-height: 160px;
  overflow-y: auto;
  font-size: 12.5px;
  color: #475569;
  line-height: 1.7;
}

.jp-warning-list {
  color: #b45309;
}

.jp-empty {
  padding: 32px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.jp-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f1f5f9;
  background: #f8fafc;
  border-radius: 0 0 14px 14px;
}

.jp-btn {
  padding: 9px 18px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
}

.jp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.jp-btn-ghost {
  background: transparent;
  color: #475569;
}

.jp-btn-primary {
  background: #2563eb;
  color: #ffffff;
}
</style>
```

- [ ] **Step 3: 数据源面板切换预览组件**

`DataSourcePanel.vue` 的 `<script setup>` 增加导入：

```js
import JsonlImportPreview from "./JsonlImportPreview.vue";
```

`onImportDone` 改为：

```js
function onImportDone(nodes, edges, inf_rules, mut_rules, options) {
  emit("import-nodes", nodes, edges, inf_rules, mut_rules, options || {});
  previewData.value = null;
}
```

模板中的预览部分替换为：

```html
    <!-- JSONL 预览面板 -->
    <JsonlImportPreview
      v-if="previewData && previewData.sourceType === 'jsonl'"
      :previewData="previewData"
      @import-done="onImportDone"
      @back="onBack"
    />

    <!-- Schema 预览面板 -->
    <SchemaPreview
      v-else-if="previewData"
      :previewData="previewData"
      @import-done="onImportDone"
      @back="onBack"
    />
```

- [ ] **Step 4: 构建验证**

Run:
```bash
cd frontend
npm run build
```
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/datasource/FileUploader.vue frontend/src/components/datasource/JsonlImportPreview.vue frontend/src/components/datasource/DataSourcePanel.vue
git commit -m "feat(frontend): 支持 JSONL 上传与导入预览"
```

---

## Task 6: 画布合并与标签展示

**Files:**
- Modify: `frontend/src/App.vue:1456-1472`
- Modify: `frontend/src/components/canvas/NodeCard.vue`

- [ ] **Step 1: onImportNodes 支持 JSONL 合并**

把 `onImportNodes` 整体替换为：

```js
function onImportNodes(importedNodes, importedEdges, importedInfRules, importedMutRules, options = {}) {
  if (!importedNodes || importedNodes.length === 0) return;

  let nodesToAdd = importedNodes;
  let edgesToAdd = importedEdges || [];

  if (options.merge) {
    const keyOf = (node) => `${node.label || ""}::${node.name || ""}`;
    const existingByKey = new Map(nodes.value.map((node) => [keyOf(node), node]));
    const idMap = new Map();
    const merged = [];

    for (const node of importedNodes) {
      const existing = existingByKey.get(keyOf(node));
      if (existing) {
        idMap.set(node.id, existing.id);
      } else {
        idMap.set(node.id, node.id);
        existingByKey.set(keyOf(node), node);
        merged.push(node);
      }
    }

    edgesToAdd = edgesToAdd
      .map((edge) => ({
        ...edge,
        source: idMap.get(edge.source) || edge.source,
        target: idMap.get(edge.target) || edge.target,
      }))
      .filter((edge) => edge.source !== edge.target);

    const seenEdges = new Set(
      edges.value.map((edge) => `${edge.source}|${edge.target}|${edge.relation}`)
    );
    edgesToAdd = edgesToAdd.filter((edge) => {
      const key = `${edge.source}|${edge.target}|${edge.relation}`;
      if (seenEdges.has(key)) return false;
      seenEdges.add(key);
      return true;
    });

    if (nodes.value.length > 0 && merged.length > 0) {
      const maxX = Math.max(...nodes.value.map((node) => node.x));
      const offsetX = maxX + 320;
      merged.forEach((node) => {
        node.x += offsetX;
      });
    }
    nodesToAdd = merged;
  }

  if (nodesToAdd.length > 0) {
    nodes.value = [...nodes.value, ...nodesToAdd];
  }
  if (edgesToAdd.length > 0) {
    edges.value = [...edges.value, ...edgesToAdd];
  }
  if (importedInfRules && importedInfRules.length > 0) {
    inferenceRules.value = [...inferenceRules.value, ...importedInfRules];
  }
  if (importedMutRules && importedMutRules.length > 0) {
    mutexRules.value = [...mutexRules.value, ...importedMutRules];
  }
  syncGraph(currentProjectId.value);
  currentPerspective.value = "process";
  statusMessage.value = "已导入数据";
}
```

- [ ] **Step 2: NodeCard 显示标签**

`NodeCard.vue` 的 `<script setup>` 把 `defineProps({...})` 改为赋值给 `props`，并加入取色函数：

```js
const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  selected: {
    type: Boolean,
    default: false
  },
  connecting: {
    type: Boolean,
    default: false
  },
  dragging: {
    type: Boolean,
    default: false
  },
  highlighted: {
    type: Boolean,
    default: false
  },
  dimmed: {
    type: Boolean,
    default: false
  },
  hasChildren: {
    type: Boolean,
    default: false
  },
  collapsed: {
    type: Boolean,
    default: false
  }
});

function labelStyle() {
  const label = props.node.label;
  if (!label) return {};
  if (label === "文件") {
    return { background: "#dbeafe", color: "#1d4ed8" };
  }
  let hue = 0;
  for (const char of label) {
    hue = (hue * 31 + char.codePointAt(0)) % 360;
  }
  return {
    background: `hsl(${hue} 85% 94%)`,
    color: `hsl(${hue} 60% 32%)`
  };
}
```

模板的 `node-body` 改为：

```html
    <!-- 节点内容区 -->
    <div class="node-body">
      <span v-if="node.label" class="node-label" :style="labelStyle()" :title="node.label">
        {{ node.label }}
      </span>
      <div class="node-id">ID: {{ node.id?.slice(0, 6) }}</div>
    </div>
```

样式区追加：

```css
.node-label {
  display: inline-block;
  max-width: 100%;
  margin-bottom: 4px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

- [ ] **Step 3: 构建验证**

Run:
```bash
cd frontend
npm run build
```
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/App.vue frontend/src/components/canvas/NodeCard.vue
git commit -m "feat(frontend): JSONL 导入按标签合并节点并展示节点标签"
```

---

## Task 7: 真实 HTTP 冒烟验证

**Files:**
- Create: `backend/scripts/smoke_jsonl_import.py`

- [ ] **Step 1: 写冒烟脚本**

创建 `backend/scripts/smoke_jsonl_import.py`：

```python
"""JSONL 导入真实 HTTP 冒烟脚本。

用法：
    cd backend
    E:/Anaconda/envs/benti-py38/python.exe scripts/smoke_jsonl_import.py http://127.0.0.1:8000
"""

import json
import os
import sys
import tempfile
import urllib.request
import uuid


SAMPLE = (
    '0{"file_name":"test.pdf","spans":['
    '{"id":1,"label":"参数","text":"33160元"},'
    '{"id":2,"label":"参数","text":"2025 年"}],'
    '"relations":[{"fromId":2,"toId":1,"type":"属于"}]}\n'
    '{"file_name":"GBT.pdf","spans":['
    '{"id":1,"label":"关键工序","text":"冷拉"}],"relations":[]}\n'
)


def multipart(field_name, file_name, content):
    boundary = "----smoke" + uuid.uuid4().hex
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
    ).encode("utf-8")
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, boundary


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE)

    with open(path, "rb") as fh:
        content = fh.read()
    body, boundary = multipart("file", "sample.jsonl", content)
    request = urllib.request.Request(
        f"{base}/api/datasource/file/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request) as response:
        uploaded = json.loads(response.read().decode("utf-8"))

    summary = uploaded.get("jsonl_summary") or {}
    print("upload:", uploaded.get("file_name"), summary.get("files"), summary.get("entities"), summary.get("relations"))
    assert summary.get("files") == 2, summary
    assert summary.get("entities") == 3, summary
    assert summary.get("relations") == 1, summary

    imported = post_json(
        f"{base}/api/datasource/jsonl/import",
        {"source_id": uploaded["file_id"]},
    )
    print("import nodes:", len(imported["nodes"]), "edges:", len(imported["edges"]))
    labels = {node["label"] for node in imported["nodes"]}
    assert "文件" in labels, labels
    assert len(imported["nodes"]) == 5, imported["nodes"]

    print("OK")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 启动后端并运行冒烟**

Run（终端 1）：
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

Run（终端 2）：
```bash
cd backend
E:/Anaconda/envs/benti-py38/python.exe scripts/smoke_jsonl_import.py http://127.0.0.1:8899
```
Expected:
```
upload: sample.jsonl 2 3 1
import nodes: 5 edges: 4
OK
```
（5 = 2 个文件节点 + 3 个实体节点；4 = 3 条「包含」边 + 1 条实体关系边）

- [ ] **Step 3: 用真实样本验证**

Run:
```bash
curl -s -X POST "http://127.0.0.1:8899/api/datasource/file/upload" -F "file=@H:/Git/Label-fast-main_混合标注/零件工艺标注/零件工艺标注/annotations.jsonl" | head -c 500
curl -s -X POST "http://127.0.0.1:8899/api/datasource/file/upload" -F "file=@H:/Git/Label-fast-main_混合标注/零件工艺标注/零件工艺标注/测试文本_annotations.jsonl" | head -c 500
```
Expected: 两个响应都包含 `"file_type":".jsonl"` 和 `jsonl_summary`，`bad_lines` 为 0

- [ ] **Step 4: 前端手工验证清单**

Run:
```bash
cd frontend
npm run build
```
然后启动应用（`start.bat` 或 `npm run dev` + 后端），逐项确认：

1. 数据导入 → 上传文件：弹窗出现，不再一闪而过
2. 上传 `测试数据/机械加工本体关系表.xlsx` → 预览 4 张表 → 确认导入 → 画布出现节点与关系
3. 中文文件名在预览页显示正常，不是乱码
4. 上传 `annotations.jsonl` → 预览显示字段映射、2 个文件、实体数、标签分布 → 确认导入
5. 画布上文件节点带「文件」标签，实体节点带各自标签
6. 再次导入同一 JSONL → 不产生重复节点

- [ ] **Step 5: 提交**

```bash
git add backend/scripts/smoke_jsonl_import.py
git commit -m "test(backend): 增加 JSONL 导入 HTTP 冒烟脚本"
```

---

## 自查记录

- 规格覆盖：Excel 浮层修复（Task 4）、中文文件名（Task 3）、Excel 异常信息（Task 3）、`label` 字段（Task 3/6）、解析容错（Task 1）、全局合并与布局（Task 2）、上传入口与预览（Task 5）、画布合并（Task 6）、测试（Task 1/2/7）
- 无占位符：所有代码步骤均给出完整实现
- 类型一致性：`parse_jsonl` → `JsonlParseResult(records/mappings/warnings/total_lines/bad_lines)` 在 Task 3 的 API 中按同名属性使用；`build_graph(records, origin, fallback_file_name)` 在 Task 2/3/7 中签名一致；前端 `{ merge: true }` 选项从 Task 5 传到 Task 6
