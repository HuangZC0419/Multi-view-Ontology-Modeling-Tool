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


class ParseJsonlTests(unittest.TestCase):
    def write_temp(self, text, suffix=".jsonl", encoding="utf-8"):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

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

        missing_keys = {
            "file_name": "a.png",
            "spans": [{"text": "甲", "label": "x"}],
            "relations": [{"type": "关联"}],
        }
        result = parse_jsonl(
            self.write_temp(json.dumps(missing_keys, ensure_ascii=False))
        )
        self.assertEqual(result.records[0]["relations"], [])
        self.assertTrue(any("from/to" in warning for warning in result.warnings))

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


if __name__ == "__main__":
    unittest.main()
