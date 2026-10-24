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
