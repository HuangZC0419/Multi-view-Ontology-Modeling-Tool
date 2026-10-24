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
