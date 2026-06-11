"""阶段 5 生产加固测试：鉴权、限流、request_id、日志脱敏、异常信封。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.logging import mask_sensitive
from app.main import app


@pytest.fixture
def client(monkeypatch):
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    monkeypatch.setattr("app.api.resume.embedding_client._unavailable", True)
    return TestClient(app)


# ---------------- 日志脱敏 ----------------

def test_mask_email():
    assert "***@***" in mask_sensitive("联系 zhang@example.com 即可")
    assert "zhang@example.com" not in mask_sensitive("zhang@example.com")


def test_mask_phone():
    out = mask_sensitive("电话 13800001111 备用")
    assert "13800001111" not in out


def test_mask_api_key():
    out = mask_sensitive("key=sk-abcdef1234567890")
    assert "sk-abcdef1234567890" not in out
    assert "sk-abc" in out  # 保留前缀便于排查


def test_mask_recurses_dict_and_list():
    out = mask_sensitive({"a": ["x@y.com"], "b": "ok"})
    assert out["a"][0] == "***@***"
    assert out["b"] == "ok"


# ---------------- request_id / 异常信封 ----------------

def test_request_id_header_present(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Request-ID")


def test_error_envelope_has_request_id(client):
    # 非法 UUID -> 400，应走统一信封
    resp = client.get("/api/v1/resumes/not-a-uuid")
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == 400
    assert "request_id" in body["error"]


# ---------------- 鉴权 ----------------

def test_auth_disabled_allows_all(client):
    # 默认 auth_enabled=False
    resp = client.get("/api/v1/resumes")
    assert resp.status_code == 200


def test_auth_enabled_rejects_without_key(client, monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "api_keys", "secret-123,secret-456")
    resp = client.get("/api/v1/resumes")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == 401


def test_auth_enabled_accepts_valid_key(client, monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "api_keys", "secret-123")
    resp = client.get("/api/v1/resumes", headers={"X-API-Key": "secret-123"})
    assert resp.status_code == 200


def test_auth_enabled_but_no_keys_allows(client, monkeypatch):
    """开启鉴权但未配置 key：放行（配置疏漏保护）。"""
    from app.core import security

    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "api_keys", "")
    resp = client.get("/api/v1/resumes")
    assert resp.status_code == 200


def test_health_open_even_with_auth(client, monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "api_keys", "secret-123")
    # health 未挂鉴权依赖，始终开放
    assert client.get("/health").status_code == 200


# ---------------- 限流 ----------------

def test_rate_limit_blocks_after_threshold(client, monkeypatch):
    from app.core import middleware

    monkeypatch.setattr(middleware.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(middleware.settings, "rate_limit_per_minute", 3)

    # 前 3 次放行，第 4 次 429
    statuses = [client.get("/api/v1/resumes").status_code for _ in range(4)]
    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


def test_rate_limit_exempts_health(client, monkeypatch):
    from app.core import middleware

    monkeypatch.setattr(middleware.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(middleware.settings, "rate_limit_per_minute", 1)
    # health 豁免，多次都 200
    assert all(client.get("/health").status_code == 200 for _ in range(5))
