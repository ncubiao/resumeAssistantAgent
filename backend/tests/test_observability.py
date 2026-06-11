"""阶段 6 可观测性测试：/metrics、/health/deep、路径归一化。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.metrics import normalize_path
from app.main import app


@pytest.fixture
def client(monkeypatch):
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    monkeypatch.setattr("app.api.resume.embedding_client._unavailable", True)
    return TestClient(app)


# ---------------- 路径归一化（基数控制） ----------------

def test_normalize_uuid():
    p = "/api/v1/resumes/3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert normalize_path(p) == "/api/v1/resumes/{id}"


def test_normalize_numeric_id():
    assert normalize_path("/items/12345") == "/items/{id}"


def test_normalize_leaves_plain_path():
    assert normalize_path("/api/v1/resumes") == "/api/v1/resumes"


# ---------------- /metrics ----------------

def test_metrics_endpoint_prometheus_format(client):
    # 先打一些流量
    client.get("/health")
    client.get("/api/v1/resumes")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds_sum" in body
    assert "llm_calls_total" in body
    # 应含 TYPE 注释
    assert "# TYPE http_requests_total counter" in body


def test_metrics_records_request_with_normalized_path(client):
    # 制造一个带 UUID 的请求
    import uuid

    client.get(f"/api/v1/resumes/{uuid.uuid4()}")  # 404
    body = client.get("/metrics").text
    # 路径应被归一化为 {id}，而不是裸 UUID
    assert "/api/v1/resumes/{id}" in body


# ---------------- /health/deep ----------------

def test_health_deep_ok(client):
    resp = client.get("/health/deep")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"]["status"] == "ok"
    assert "vector_store" in data["checks"]
    assert "llm" in data["checks"]


def test_health_deep_db_failure_returns_503(client, monkeypatch):
    # 模拟 DB 故障：让 session_scope 抛错
    import app.core.database as db

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "session_scope", _boom)
    resp = client.get("/health/deep")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
