"""阶段 3 新增 API 端到端测试：/agent/analyze、/matches、/optimize。

强制关闭 LLM 走 heuristic 路径，确保离线、确定性。
所有端点都接 DB；CRUD fixture 复用 conftest 的 _isolated_db。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    # 关闭 LLM 与 embedding，避免真实网络调用
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    monkeypatch.setattr("app.api.resume.embedding_client._unavailable", True)
    return TestClient(app)


def _create_resume(client, text: str) -> str:
    resp = client.post("/api/v1/resumes/parse-text", json={"text": text})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------- /agent/analyze ----------------

def test_agent_analyze_with_resume_id_and_jd_both_mode(client):
    rid = _create_resume(client, "张三，本科，Python FastAPI Docker，3年经验")
    resp = client.post(
        "/api/v1/agent/analyze",
        json={"resume_id": rid, "jd": "Python 后端，熟 FastAPI", "mode": "both"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "both"
    assert data["parsed_resume"] is not None
    assert "skills" in data["analysis"]
    assert data["match"] is not None
    assert data["optimize"] is not None
    nodes = [t["node"] for t in data["trace"]]
    assert nodes == ["parser", "analyzer", "matcher", "optimizer"]
    assert data["thread_id"]


def test_agent_analyze_raw_text_optimize_only(client):
    resp = client.post(
        "/api/v1/agent/analyze",
        json={"raw_text": "李四，前端工程师，React TypeScript", "mode": "optimize"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["match"] is None
    assert data["optimize"] is not None


def test_agent_analyze_requires_input(client):
    resp = client.post("/api/v1/agent/analyze", json={})
    assert resp.status_code == 400


def test_agent_analyze_invalid_resume_id(client):
    resp = client.post("/api/v1/agent/analyze", json={"resume_id": "not-uuid"})
    assert resp.status_code == 400


def test_agent_analyze_missing_resume_returns_404(client):
    import uuid

    resp = client.post("/api/v1/agent/analyze", json={"resume_id": str(uuid.uuid4())})
    assert resp.status_code == 404


# ---------------- /matches ----------------

def test_match_single(client):
    rid = _create_resume(client, "Python 后端 5 年，FastAPI、PostgreSQL")
    resp = client.post(
        "/api/v1/matches/single",
        json={"resume_id": rid, "jd": "招聘 Python 后端，FastAPI 经验"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resume_id"] == rid
    assert 0 <= data["overall_score"] <= 100


def test_match_single_invalid_id(client):
    resp = client.post("/api/v1/matches/single", json={"resume_id": "abc", "jd": "x"})
    assert resp.status_code == 400


def test_match_single_missing_resume(client):
    import uuid

    resp = client.post(
        "/api/v1/matches/single",
        json={"resume_id": str(uuid.uuid4()), "jd": "x"},
    )
    assert resp.status_code == 404


def test_match_batch_sorts_by_score(client):
    rid1 = _create_resume(client, "Python FastAPI 后端")
    rid2 = _create_resume(client, "UI 设计师 Figma")
    resp = client.post(
        "/api/v1/matches/batch",
        json={"resume_ids": [rid2, rid1], "jd": "Python 后端开发"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["jd"] == "Python 后端开发"
    scores = [r["overall_score"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True)  # 降序


def test_match_batch_empty_ids(client):
    resp = client.post("/api/v1/matches/batch", json={"resume_ids": [], "jd": "x"})
    assert resp.status_code == 400


# ---------------- /optimize ----------------

def test_optimize_suggestions(client):
    rid = _create_resume(client, "实习生，Python 半年")
    resp = client.post(
        "/api/v1/optimize/suggestions",
        json={"resume_id": rid, "target_jd": "Python 后端"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resume_id"] == rid
    # 无 LLM 时 fallback 也至少给 1 条
    assert len(data["suggestions"]) >= 1
    sug = data["suggestions"][0]
    assert "category" in sug and "improved" in sug


def test_optimize_rewrite_offline_fallback(client):
    """LLM 关闭时，rewrite 应返回去除多余空白的版本，不报错。"""
    resp = client.post(
        "/api/v1/optimize/rewrite",
        json={"paragraph": "  我  做了    很多   事情  ", "target_role": "后端"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original"]
    # fallback：多余空白合并为单空格
    assert "  " not in data["rewritten"]


def test_optimize_rewrite_empty_rejected(client):
    resp = client.post("/api/v1/optimize/rewrite", json={"paragraph": "  "})
    assert resp.status_code == 400
