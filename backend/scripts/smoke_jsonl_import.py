"""JSONL 导入真实 HTTP 冒烟脚本。

用法：
    cd backend
    E:/Anaconda/envs/benti-py38/python.exe scripts/smoke_jsonl_import.py http://127.0.0.1:8000
"""

import json
import os
import sys
import tempfile
import urllib.error
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


def upload_request(base, file_name, content):
    body, boundary = multipart("file", file_name, content)
    return urllib.request.Request(
        f"{base}/api/datasource/file/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def json_request(url, payload):
    data = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )


def post_json(url, payload):
    with urllib.request.urlopen(json_request(url, payload)) as response:
        return json.loads(response.read().decode("utf-8"))


def upload(base, file_name, content):
    with urllib.request.urlopen(upload_request(base, file_name, content)) as response:
        return json.loads(response.read().decode("utf-8"))


def expect_error(request, status, detail_contains=None):
    try:
        with urllib.request.urlopen(request):
            pass
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        assert exc.code == status, (exc.code, status, body)
        if detail_contains is not None:
            try:
                detail = json.loads(body).get("detail", "")
            except ValueError:
                detail = body
            assert detail_contains in str(detail), detail
        return body
    raise AssertionError(f"期望 HTTP {status}，但请求成功")


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE)

    with open(path, "rb") as fh:
        content = fh.read()
    uploaded = upload(base, "sample.jsonl", content)

    summary = uploaded.get("jsonl_summary") or {}
    print("upload:", uploaded.get("file_name"), summary.get("files"), summary.get("entities"), summary.get("relations"))
    assert summary.get("files") == 2, summary
    assert summary.get("entities") == 3, summary
    assert summary.get("relations") == 1, summary
    assert summary.get("total_lines") == 2, summary

    imported = post_json(
        f"{base}/api/datasource/jsonl/import",
        {"source_id": uploaded["file_id"]},
    )
    print("import nodes:", len(imported["nodes"]), "edges:", len(imported["edges"]))
    labels = {node["label"] for node in imported["nodes"]}
    assert "文件" in labels, labels
    assert len(imported["nodes"]) == 5, imported["nodes"]
    assert imported["summary"].get("total_lines") == 2, imported["summary"]

    # 中文文件名：multipart 头里的 filename 用 UTF-8 字节传递，响应必须还原原文
    chinese = upload(base, "中文标注.jsonl", content)
    print("upload chinese filename:", chinese.get("file_name"))
    assert chinese.get("file_name") == "中文标注.jsonl", chinese
    assert (chinese.get("jsonl_summary") or {}).get("files") == 2, chinese

    # 非法 source_id：路径穿越必须被拒绝
    expect_error(
        json_request(
            f"{base}/api/datasource/jsonl/import",
            {"source_id": "../users"},
        ),
        400,
        "非法的文件标识",
    )

    # 合法但不存在的 UUID
    expect_error(
        json_request(
            f"{base}/api/datasource/jsonl/import",
            {"source_id": "00000000-0000-4000-8000-000000000000"},
        ),
        404,
    )

    # 空 JSONL：上传可成功，但导入必须返回 400
    empty = upload(base, "empty.jsonl", b"")
    assert (empty.get("jsonl_summary") or {}).get("total_lines") == 0, empty
    expect_error(
        json_request(
            f"{base}/api/datasource/jsonl/import",
            {"source_id": empty["file_id"]},
        ),
        400,
        "未识别到有效记录",
    )

    # 损坏的 xlsx：解析异常必须透传为 400 而不是 500
    expect_error(
        upload_request(base, "broken.xlsx", b"this is not an excel file"),
        400,
        "文件解析失败",
    )

    print("OK")


if __name__ == "__main__":
    main()
