"""语义检索端点测试（聚焦无 embedding 时的关键词降级路径）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    # 强制关闭 embedding，走关键词检索 fallback（离线、确定性）
    # available 是 property，不能直接 setattr；改设底层 _unavailable 标志
    monkeypatch.setattr("app.api.resume.embedding_client._unavailable", True)
    return TestClient(app)


def _create(client, text):
    resp = client.post("/api/v1/resumes/parse-text", json={"text": text})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_keyword_search_hits_relevant_resume(client):
    _create(client, "王五，资深 Python 后端，精通 FastAPI、PostgreSQL")
    _create(client, "赵六，前端工程师，React 与 TypeScript")

    resp = client.post("/api/v1/resumes/search", json={"query": "FastAPI PostgreSQL", "k": 5})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    # 命中的应是 Python 后端那份
    assert any("Python" in (r.get("raw_text") or "") for r in results)


def test_search_empty_query_rejected(client):
    assert client.post("/api/v1/resumes/search", json={"query": "  ", "k": 3}).status_code == 400


def test_search_no_match_returns_empty(client):
    _create(client, "纯文本无关内容 abcdef")
    resp = client.post("/api/v1/resumes/search", json={"query": "完全不相关的查询词zzzzz", "k": 5})
    assert resp.status_code == 200
    assert resp.json() == []
