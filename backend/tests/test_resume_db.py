"""简历持久化（DB CRUD）端到端测试。

无 LLM key 时 parser 走 heuristic、embedding 走降级，依然应全链路跑通。
为保持离线 + 快速，这里显式关闭 embedding（避免真实网络调用），
向量检索的 fallback 路径在 test_search.py 单独覆盖。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    # 关闭 embedding，确保 CRUD 测试不发起真实网络请求
    # available 是 property，不能直接 setattr；改设底层 _unavailable 标志
    monkeypatch.setattr("app.api.resume.embedding_client._unavailable", True)
    return TestClient(app)


def _create(client, text="张三\nPython 工程师，5年经验，熟悉 FastAPI 和 Docker"):
    resp = client.post("/api/v1/resumes/parse-text", json={"text": text})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_parse_text_persists_and_returns_id(client):
    data = _create(client)
    assert data["id"]
    assert data["raw_text"]


def test_list_after_create(client):
    _create(client)
    resp = client.get("/api/v1/resumes")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_by_id_roundtrip(client):
    created = _create(client)
    rid = created["id"]
    resp = client.get(f"/api/v1/resumes/{rid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rid


def test_dedup_same_content_returns_same_record(client):
    text = "李四\nGo 后端开发"
    first = _create(client, text)
    second = _create(client, text)
    assert first["id"] == second["id"]
    # 库里应只有一条
    listing = client.get("/api/v1/resumes").json()
    assert sum(1 for r in listing if r["id"] == first["id"]) == 1


def test_update_resume(client):
    rid = _create(client)["id"]
    resp = client.put(f"/api/v1/resumes/{rid}", json={"name": "新名字", "skills": ["python", "k8s"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "新名字"
    assert "k8s" in body["skills"]


def test_delete_resume(client):
    rid = _create(client)["id"]
    assert client.delete(f"/api/v1/resumes/{rid}").status_code == 200
    assert client.get(f"/api/v1/resumes/{rid}").status_code == 404


def test_invalid_uuid_returns_400(client):
    assert client.get("/api/v1/resumes/not-a-uuid").status_code == 400


def test_missing_resume_returns_404(client):
    import uuid

    assert client.get(f"/api/v1/resumes/{uuid.uuid4()}").status_code == 404


def test_empty_text_rejected(client):
    assert client.post("/api/v1/resumes/parse-text", json={"text": "   "}).status_code == 400
