import json
import os
import tempfile
import unittest

from app.services.jsonl_import import (
    CARD_H,
    CARD_W,
    MAX_WARNINGS,
    build_graph,
    parse_jsonl,
)


SAMPLE_A = (
    '0{"file_name":"test.pdf","text":"2025 年个人酬金查询\\n2025 年税后实发金额33160元",'
    '"spans":[{"id":1,"start":25,"end":31,"label":"参数","text":"33160元"},'
    '{"id":2,"start":13,"end":19,"label":"参数","text":"2025 年"}],'
    '"relations":[{"fromId":2,"toId":1,"type":"属于"}]}\n'
    '{"file_name":"GBT+4423-2020.pdf","text":"标准正文",'
    '"spans":[{"id":1,"label":"关键工序","text":"冷拉"}],"relations":[]}\n'
)


class TempFileMixin:
    """测试用例共用的临时文件写入助手（普通 mixin，不继承 TestCase）。"""

    def write_temp(self, text, suffix=".jsonl", encoding="utf-8"):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path


class ParseJsonlTests(TempFileMixin, unittest.TestCase):
    def test_tolerates_leading_garbage_prefix(self):
        result = parse_jsonl(self.write_temp(SAMPLE_A))
        self.assertEqual(result.bad_lines, 0)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.mappings["file"], "file_name")
        self.assertEqual(result.mappings["entities"], "spans")
        self.assertEqual(result.mappings["relations"], "relations")

    def test_relation_resolves_by_numeric_id(self):
        result = parse_jsonl(self.write_temp(SAMPLE_A))
        entities = result.records[0]["entities"]
        relation = result.records[0]["relations"][0]
        self.assertEqual(relation["type"], "属于")
        self.assertEqual(relation["source"], entities[1]["id"])  # fromId=2
        self.assertEqual(relation["target"], entities[0]["id"])  # toId=1

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
        result = parse_jsonl(self.write_temp(text))
        self.assertEqual(len(result.records), 3)

    def test_bad_line_is_counted(self):
        result = parse_jsonl(
            self.write_temp('{"file_name":"a.png","spans":[]}\nnot json\n')
        )
        self.assertEqual(result.bad_lines, 1)
        self.assertEqual(len(result.records), 1)

    def test_json_array_file(self):
        text = json.dumps(
            [{"file_name": "a.png", "spans": [{"text": "甲", "label": "x"}]}],
            ensure_ascii=False,
        )
        result = parse_jsonl(self.write_temp(text))
        self.assertEqual(len(result.records), 1)

    def test_json_array_with_dirty_prefix(self):
        text = "0" + json.dumps(
            [{"file_name": "a.png", "spans": [{"text": "甲", "label": "x"}]}],
            ensure_ascii=False,
        )
        result = parse_jsonl(self.write_temp(text))
        self.assertEqual(result.bad_lines, 0)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["file_name"], "a.png")
        self.assertEqual(result.mappings["entities"], "spans")

    def test_relation_endpoint_by_entity_text(self):
        record = {
            "file_name": "a.png",
            "entities": [
                {"text": "甲", "label": "x"},
                {"text": "乙", "label": "x"},
            ],
            "relations": [{"from": "甲", "to": "乙", "type": "关联"}],
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual(len(result.records[0]["relations"]), 1)

    def test_gbk_encoding(self):
        path = self.write_temp(
            json.dumps(
                {"file_name": "标准.pdf", "spans": [{"text": "甲", "label": "x"}]},
                ensure_ascii=False,
            ),
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
        result = parse_jsonl(
            self.write_temp(json.dumps(with_spans, ensure_ascii=False))
        )
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["甲"])

        no_spans = {
            "file_name": "a.png",
            "annotations": [{"text": "乙", "label": "汇总"}],
        }
        result = parse_jsonl(self.write_temp(json.dumps(no_spans, ensure_ascii=False)))
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["乙"])

    def test_empty_spans_falls_back_to_annotations(self):
        record = {
            "file_name": "a.png",
            "spans": [],
            "annotations": [{"text": "乙", "label": "汇总"}],
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["乙"])
        self.assertEqual(result.mappings["entities"], "annotations")

    def test_fallback_file_name(self):
        record = {"spans": [{"text": "甲", "label": "x"}]}
        result = parse_jsonl(
            self.write_temp(json.dumps(record, ensure_ascii=False)),
            fallback_file_name="fallback.pdf",
        )
        self.assertEqual(result.records[0]["file_name"], "fallback.pdf")
        self.assertNotIn("file", result.mappings)

        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual(result.records[0]["file_name"], "未命名文件")

    def test_source_path_used_as_file(self):
        record = {
            "source_path": "docs\\标准.pdf",
            "spans": [{"text": "甲", "label": "x"}],
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual(result.records[0]["file_name"], "标准.pdf")
        self.assertEqual(result.mappings["file"], "source_path")

    def test_empty_or_non_scalar_entity_fields_are_skipped(self):
        record = {
            "file_name": "a.png",
            "spans": [
                {"text": "", "label": "x"},
                {"label": "x"},
                {"text": {"nested": 1}, "label": {"nested": 2}},
                {"text": "甲", "label": "x"},
            ],
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["甲"])

    def test_duplicate_raw_id_within_record_gets_unique_ids_and_warning(self):
        record = {
            "file_name": "a.png",
            "spans": [
                {"id": 1, "text": "甲", "label": "x"},
                {"id": 1, "text": "乙", "label": "x"},
            ],
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        entities = result.records[0]["entities"]
        self.assertEqual(len(entities), 2)
        self.assertNotEqual(entities[0]["id"], entities[1]["id"])
        self.assertTrue(any("重复" in warning for warning in result.warnings))

    def test_ids_are_unique_across_records(self):
        text = (
            json.dumps({"spans": [{"id": 1, "text": "甲", "label": "x"}]}) + "\n"
            + json.dumps({"spans": [{"id": 1, "text": "乙", "label": "x"}]}) + "\n"
        )
        result = parse_jsonl(self.write_temp(text, encoding="utf-8"))
        self.assertNotEqual(
            result.records[0]["entities"][0]["id"],
            result.records[1]["entities"][0]["id"],
        )

    def test_unmatched_relation_endpoint_warns(self):
        record = {
            "file_name": "a.png",
            "spans": [{"text": "甲", "label": "x"}],
            "relations": [{"from": "甲", "to": "不存在", "type": "关联"}],
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual(result.records[0]["relations"], [])
        self.assertTrue(any("无法匹配" in warning for warning in result.warnings))

        invalid_relations = {
            "file_name": "a.png",
            "spans": [{"text": "甲", "label": "x"}],
            "relations": [{"type": "关联"}],
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(invalid_relations, ensure_ascii=False))
        )
        # 无效的顶层关系数组现在被忽略，以便后续别名或嵌套兜底接管
        self.assertEqual(result.records[0]["relations"], [])

    def test_nested_entity_structure_is_detected(self):
        record = {
            "file_name": "a.png",
            "data": {"entities": [{"text": "甲", "label": "x"}]},
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual([e["text"] for e in result.records[0]["entities"]], ["甲"])
        self.assertEqual(result.mappings["entities"], "data.entities")

    def test_nested_relation_structure_is_detected(self):
        record = {
            "file_name": "a.png",
            "data": {
                "entities": [
                    {"text": "甲", "label": "x"},
                    {"text": "乙", "label": "x"},
                ],
                "links": [{"from": "甲", "to": "乙", "type": "关联"}],
            },
        }
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertEqual(len(result.records[0]["relations"]), 1)
        self.assertEqual(result.mappings["relations"], "data.links")

    def test_mappings_only_written_for_non_empty_arrays(self):
        record = {"file_name": "a.png", "spans": [], "relations": []}
        result = parse_jsonl(self.write_temp(json.dumps(record, ensure_ascii=False)))
        self.assertNotIn("entities", result.mappings)
        self.assertNotIn("relations", result.mappings)
        self.assertEqual(result.mappings["file"], "file_name")

    def test_lone_surrogate_is_cleaned(self):
        text = (
            '{"file_name":"a.png","spans":'
            '[{"text":"\\ud800甲","label":"x"}]}'
        )
        result = parse_jsonl(self.write_temp(text))
        entity = result.records[0]["entities"][0]
        self.assertIn("甲", entity["text"])
        entity["text"].encode("utf-8")

    def test_utf16_bom_file_is_decoded(self):
        payload = {
            "file_name": "标准.pdf",
            "spans": [{"text": "甲", "label": "x"}],
        }
        path = self.write_temp(
            json.dumps(payload, ensure_ascii=False), encoding="utf-16"
        )
        result = parse_jsonl(path)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["file_name"], "标准.pdf")
        self.assertEqual(
            [e["text"] for e in result.records[0]["entities"]], ["甲"]
        )

    def test_all_bad_lines_warning_respects_limit(self):
        text = "坏行\n" * (MAX_WARNINGS + 5)
        result = parse_jsonl(self.write_temp(text))
        self.assertEqual(result.bad_lines, MAX_WARNINGS + 5)
        self.assertEqual(len(result.warnings), MAX_WARNINGS)
        self.assertIn("编码不匹配", result.warnings[0])

        single = parse_jsonl(self.write_temp("坏行\n"))
        self.assertEqual(single.bad_lines, 1)
        self.assertIn("编码不匹配", single.warnings[0])

    def test_deeply_nested_array_does_not_raise_and_counts_as_bad(self):
        depth = 3000
        text = "[" * depth + "]" * depth
        result = parse_jsonl(self.write_temp(text))
        self.assertEqual(result.records, [])
        self.assertEqual(result.total_lines, 1)
        self.assertEqual(result.bad_lines, 1)

    def test_nested_search_depth_limit_and_non_data_subtree_skipped(self):
        at_limit = {
            "file_name": "a.png",
            "a": {"b": {"entities": [{"text": "甲", "label": "x"}]}},
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(at_limit, ensure_ascii=False))
        )
        self.assertEqual(
            [e["text"] for e in result.records[0]["entities"]], ["甲"]
        )
        self.assertEqual(result.mappings["entities"], "a.b.entities")

        beyond_limit = {
            "file_name": "a.png",
            "a": {"b": {"c": {"entities": [{"text": "甲", "label": "x"}]}}},
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(beyond_limit, ensure_ascii=False))
        )
        self.assertEqual(result.records[0]["entities"], [])
        self.assertNotIn("entities", result.mappings)

        under_metadata = {
            "file_name": "a.png",
            "metadata": {"entities": [{"text": "乙", "label": "x"}]},
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(under_metadata, ensure_ascii=False))
        )
        self.assertEqual(result.records[0]["entities"], [])
        self.assertNotIn("entities", result.mappings)

    def test_nested_weak_alias_requires_text_field(self):
        record = {
            "file_name": "a.png",
            "config": {"labels": [{"name": "cat"}]},
            "data": {"annotations": [{"text": "甲", "label": "x"}]},
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(record, ensure_ascii=False))
        )
        self.assertEqual(
            [e["text"] for e in result.records[0]["entities"]], ["甲"]
        )
        self.assertEqual(result.mappings["entities"], "data.annotations")

    def test_top_level_weak_alias_with_strings_is_rejected(self):
        record = {
            "labels": ["cat", "dog"],
            "annotations": [{"text": "甲", "label": "x"}],
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(record, ensure_ascii=False))
        )
        self.assertEqual(
            [e["text"] for e in result.records[0]["entities"]], ["甲"]
        )
        self.assertEqual(result.mappings["entities"], "annotations")

    def test_top_level_strong_alias_without_text_is_rejected(self):
        record = {
            "spans": [{"name": "cat"}],
            "annotations": [{"text": "乙", "label": "x"}],
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(record, ensure_ascii=False))
        )
        self.assertEqual(
            [e["text"] for e in result.records[0]["entities"]], ["乙"]
        )
        self.assertEqual(result.mappings["entities"], "annotations")

    def test_invalid_top_level_relations_fall_back_to_links(self):
        record = {
            "relations": [{"foo": 1}],
            "links": [{"source": "甲", "target": "乙", "type": "关联"}],
            "spans": [
                {"id": "1", "text": "甲", "label": "x"},
                {"id": "2", "text": "乙", "label": "x"},
            ],
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(record, ensure_ascii=False))
        )
        self.assertEqual(len(result.records[0]["relations"]), 1)
        self.assertEqual(result.mappings["relations"], "links")

    def test_relation_can_reference_entity_in_another_record(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":1,"text":"A"},{"id":2,"text":"B"}]}\n'
            '{"file_name":"a.pdf","relations":[{"fromId":1,"toId":2}]}\n'
        )
        result = parse_jsonl(self.write_temp(text))
        self.assertEqual(len(result.records[1]["relations"]), 1)
        relation = result.records[1]["relations"][0]
        entities = result.records[0]["entities"]
        self.assertEqual(relation["source"], entities[0]["id"])
        self.assertEqual(relation["target"], entities[1]["id"])
        self.assertFalse(
            any("无法匹配" in warning for warning in result.warnings)
        )


class BuildGraphTests(TempFileMixin, unittest.TestCase):
    def test_global_merge_across_files(self):
        text = (
            '{"file_name":"a.pdf","spans":[{"id":"1","label":"参数","text":"2025 年"}]}\n'
            '{"file_name":"b.pdf","spans":[{"id":"1","label":"参数","text":"2025 年"}]}\n'
        )
        nodes, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records, origin="jsonl:test"
        )
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
        _, _, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        self.assertEqual(summary["entities"], 2)

    def test_duplicate_relation_is_deduped(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},{"id":"2","label":"x","text":"乙"}],'
            '"relations":[{"fromId":"1","toId":"2","type":"关联"},'
            '{"fromId":"1","toId":"2","type":"关联"}]}\n'
        )
        _, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        relations = [e for e in edges if e["relation"] == "关联"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(summary["relations"], 1)

    def test_positions_are_deterministic_and_unique(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},{"id":"2","label":"x","text":"乙"}]}\n'
        )
        nodes1, _, _ = build_graph(parse_jsonl(self.write_temp(text)).records)
        nodes2, _, _ = build_graph(parse_jsonl(self.write_temp(text)).records)
        positions1 = sorted(
            (round(n["x"], 3), round(n["y"], 3)) for n in nodes1
        )
        positions2 = sorted(
            (round(n["x"], 3), round(n["y"], 3)) for n in nodes2
        )
        self.assertEqual(positions1, positions2)
        self.assertEqual(len({(n["x"], n["y"]) for n in nodes1}), len(nodes1))

    def test_entity_text_is_preserved_raw(self):
        text = (
            '{"file_name":"a.pdf","spans":'
            '[{"id":"1","label":"x","text":"<b>&"}]}\n'
        )
        nodes, _, _ = build_graph(parse_jsonl(self.write_temp(text)).records)
        self.assertIn("<b>&", {n["name"] for n in nodes})

    def test_file_label_and_origin(self):
        text = '{"file_name":"a.pdf","spans":[]}\n'
        nodes, _, _ = build_graph(
            parse_jsonl(self.write_temp(text)).records, origin="jsonl:x.jsonl"
        )
        self.assertEqual(nodes[0]["label"], "文件")
        self.assertEqual(nodes[0]["origin"], "jsonl:x.jsonl")

    def test_relation_typed_containment_is_counted(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},'
            '{"id":"2","label":"x","text":"乙"},'
            '{"id":"3","label":"x","text":"丙"}],'
            '"relations":[{"fromId":"1","toId":"2","type":"包含"},'
            '{"fromId":"2","toId":"3","type":"包含"},'
            '{"fromId":"1","toId":"3","type":"包含"}]}\n'
        )
        _, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        self.assertEqual(summary["relations"], 3)
        self.assertEqual(len(edges), 6)  # 3 条实体关系 + 3 条文件包含边
        self.assertEqual(len(summary["sample_edges"]), 3)
        self.assertTrue(
            all(e["relation"] == "包含" for e in summary["sample_edges"])
        )

    def test_global_merge_relation_targets_shared_node(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},'
            '{"id":"2","label":"x","text":"乙"}],'
            '"relations":[{"fromId":"1","toId":"2","type":"关联"}]}\n'
            '{"file_name":"b.pdf","spans":[{"id":"1","label":"x","text":"甲"}]}\n'
        )
        nodes, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        entity_nodes = [n for n in nodes if n["label"] == "x"]
        names = [n["name"] for n in entity_nodes]
        self.assertEqual(names.count("甲"), 1)
        self.assertEqual(names.count("乙"), 1)
        names_by_id = {n["id"]: n["name"] for n in entity_nodes}
        relation = [e for e in edges if e["relation"] == "关联"][0]
        self.assertEqual(names_by_id[relation["source"]], "甲")
        self.assertEqual(names_by_id[relation["target"]], "乙")
        self.assertEqual(summary["entities"], 2)

    def test_same_file_records_share_one_file_node(self):
        text = (
            '{"file_name":"a.pdf","spans":[{"id":"1","label":"x","text":"甲"}]}\n'
            '{"file_name":"a.pdf","spans":[{"id":"1","label":"x","text":"甲"}]}\n'
        )
        nodes, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        self.assertEqual(
            len([n for n in nodes if n["label"] == "文件"]), 1
        )
        self.assertEqual(
            len([e for e in edges if e["relation"] == "包含"]), 1
        )
        self.assertEqual(summary["files"], 1)
        self.assertEqual(summary["entities"], 1)

    def test_empty_records_produce_empty_graph(self):
        nodes, edges, summary = build_graph([])
        self.assertEqual(nodes, [])
        self.assertEqual(edges, [])
        self.assertEqual(summary["records"], 0)
        self.assertEqual(summary["files"], 0)
        self.assertEqual(summary["entities"], 0)
        self.assertEqual(summary["relations"], 0)
        self.assertEqual(summary["unresolved_relations"], 0)
        self.assertEqual(summary["labels"], {})
        self.assertEqual(summary["file_names"], [])
        self.assertEqual(summary["sample_nodes"], [])
        self.assertEqual(summary["sample_edges"], [])

    def test_file_without_entities(self):
        text = '{"file_name":"a.pdf","spans":[]}\n'
        nodes, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        self.assertEqual(summary["entities"], 0)
        self.assertEqual([n["label"] for n in nodes], ["文件"])
        self.assertEqual(edges, [])

    def test_self_loop_relation_is_dropped(self):
        text = (
            '{"file_name":"a.pdf","spans":[{"id":"1","label":"x","text":"甲"}],'
            '"relations":[{"fromId":"1","toId":"1","type":"关联"}]}\n'
        )
        _, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        self.assertEqual([e for e in edges if e["relation"] == "关联"], [])
        self.assertEqual(len(edges), 1)  # 仅保留文件包含边
        self.assertEqual(summary["relations"], 0)

    def test_missing_relation_type_falls_back(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},'
            '{"id":"2","label":"x","text":"乙"}],'
            '"relations":[{"fromId":"1","toId":"2"}]}\n'
        )
        _, edges, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        self.assertEqual(len([e for e in edges if e["relation"] == "关联"]), 1)
        self.assertEqual(summary["relations"], 1)
        sample = summary["sample_edges"][0]
        self.assertEqual(sample["source_name"], "甲")
        self.assertEqual(sample["target_name"], "乙")

    def test_entity_label_named_file_is_rewritten(self):
        text = (
            '{"file_name":"a.pdf","spans":'
            '[{"id":"1","label":"文件","text":"甲"}]}\n'
        )
        nodes, _, summary = build_graph(
            parse_jsonl(self.write_temp(text)).records
        )
        by_name = {n["name"]: n for n in nodes}
        self.assertEqual(by_name["a.pdf"]["label"], "文件")
        self.assertEqual(by_name["甲"]["label"], "实体")
        self.assertEqual(summary["labels"], {"实体": 1})

    def test_file_name_is_preserved_raw(self):
        text = '{"file_name":"a&b<c>.pdf","spans":[]}\n'
        nodes, _, _ = build_graph(parse_jsonl(self.write_temp(text)).records)
        self.assertEqual(nodes[0]["name"], "a&b<c>.pdf")

    def test_fallback_file_name_is_used(self):
        records = [{"file_name": "", "entities": [], "relations": []}]
        nodes, _, summary = build_graph(
            records, fallback_file_name="fb.pdf"
        )
        self.assertEqual(nodes[0]["name"], "fb.pdf")
        self.assertEqual(summary["file_names"], ["fb.pdf"])

    def test_labels_count_and_order(self):
        spans = [
            {"id": "1", "label": "A", "text": "甲"},
            {"id": "2", "label": "B", "text": "乙"},
            {"id": "3", "label": "A", "text": "丙"},
        ]
        text = json.dumps(
            {"file_name": "a.pdf", "spans": spans}, ensure_ascii=False
        )
        _, _, summary = build_graph(parse_jsonl(self.write_temp(text)).records)
        self.assertEqual(summary["labels"], {"A": 2, "B": 1})
        self.assertEqual(list(summary["labels"]), ["A", "B"])

    def test_cross_record_relation_is_built(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":1,"text":"A"},{"id":2,"text":"B"}]}\n'
            '{"file_name":"a.pdf","relations":['
            '{"fromId":1,"toId":2,"type":"关联"}]}\n'
        )
        records = parse_jsonl(self.write_temp(text)).records
        nodes, edges, summary = build_graph(records)
        relations = [e for e in edges if e["relation"] == "关联"]
        self.assertEqual(len(relations), 1)
        node_names = {n["id"]: n["name"] for n in nodes}
        self.assertEqual(node_names[relations[0]["source"]], "A")
        self.assertEqual(node_names[relations[0]["target"]], "B")
        self.assertEqual(summary["relations"], 1)
        self.assertEqual(summary["unresolved_relations"], 0)

    def test_relation_record_before_entity_record_is_built(self):
        text = (
            '{"file_name":"a.pdf","relations":['
            '{"fromId":1,"toId":2,"type":"关联"}]}\n'
            '{"file_name":"a.pdf","spans":['
            '{"id":1,"text":"A"},{"id":2,"text":"B"}]}\n'
        )
        records = parse_jsonl(self.write_temp(text)).records
        nodes, edges, summary = build_graph(records)
        relations = [e for e in edges if e["relation"] == "关联"]
        self.assertEqual(len(relations), 1)
        node_names = {n["id"]: n["name"] for n in nodes}
        self.assertEqual(node_names[relations[0]["source"]], "A")
        self.assertEqual(node_names[relations[0]["target"]], "B")
        self.assertEqual(summary["relations"], 1)
        self.assertEqual(summary["unresolved_relations"], 0)

    def test_mixed_relation_array_keeps_valid_edge_and_warns(self):
        text = (
            '{"file_name":"a.pdf","spans":['
            '{"id":"1","label":"x","text":"甲"},'
            '{"id":"2","label":"x","text":"乙"}],'
            '"relations":[{"fromId":"1","toId":"2","type":"关联"},'
            '{"type":"关联"}]}\n'
        )
        result = parse_jsonl(self.write_temp(text))
        self.assertTrue(
            any("from/to" in warning for warning in result.warnings)
        )
        self.assertEqual(len(result.records[0]["relations"]), 1)
        _, edges, summary = build_graph(result.records)
        self.assertEqual(len([e for e in edges if e["relation"] == "关联"]), 1)
        self.assertEqual(summary["relations"], 1)
        self.assertEqual(summary["unresolved_relations"], 0)

    def test_unresolved_relation_is_counted(self):
        records = [{
            "file_name": "a.pdf",
            "entities": [
                {"id": "0:id:1", "raw_id": "1", "text": "A", "label": "x"}
            ],
            "relations": [
                {"source": "0:id:1", "target": "0:id:999", "type": "关联"}
            ],
        }]
        nodes, edges, summary = build_graph(records)
        self.assertEqual([e for e in edges if e["relation"] == "关联"], [])
        self.assertEqual(summary["unresolved_relations"], 1)

    def test_layout_rectangles_do_not_overlap(self):
        lines = []
        for file_index in range(4):
            spans = [
                {
                    "id": "{0}-{1}".format(file_index, entity_index),
                    "label": "x",
                    "text": "t{0}-{1}".format(file_index, entity_index),
                }
                for entity_index in range(12)
            ]
            lines.append(
                json.dumps(
                    {"file_name": "f{0}.pdf".format(file_index), "spans": spans},
                    ensure_ascii=False,
                )
            )
        nodes, _, _ = build_graph(
            parse_jsonl(self.write_temp("\n".join(lines))).records
        )
        self.assertEqual(len(nodes), 52)
        for index, first in enumerate(nodes):
            for second in nodes[index + 1:]:
                self.assertTrue(
                    abs(first["x"] - second["x"]) >= CARD_W
                    or abs(first["y"] - second["y"]) >= CARD_H,
                    "节点矩形重叠：{0} 与 {1}".format(first, second),
                )


if __name__ == "__main__":
    unittest.main()
