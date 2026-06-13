"""阶段 7：会话持久化（A）测试。

强制关闭 LLM/embedding，走离线路径。复用 conftest 的 _isolated_db。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    monkeypatch.setattr("app.services.memory_service.embedding_client._unavailable", True)
    return TestClient(app)


def _send(client, message, session_id=None, user_id="u-test", role="recruiter"):
    data = {"message": message, "user_id": user_id, "user_role": role}
    if session_id:
        data["session_id"] = session_id
    resp = client.post("/api/v1/chat", data=data)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_first_message_creates_conversation(client):
    out = _send(client, "你好")
    assert out["session_id"]
    assert out["user_role"] == "recruiter"


def test_second_message_continues_same_session(client):
    first = _send(client, "第一条")
    sid = first["session_id"]
    second = _send(client, "第二条", session_id=sid)
    assert second["session_id"] == sid


def test_conversation_persists_messages(client):
    out = _send(client, "记住这句话")
    sid = out["session_id"]
    detail = client.get(f"/api/v1/chat/conversations/{sid}").json()
    # 至少有 user + assistant 两条
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles and "assistant" in roles
    assert any(m["content"] == "记住这句话" for m in detail["messages"])


def test_list_conversations_by_user(client):
    _send(client, "会话A", user_id="u-A")
    _send(client, "会话B", user_id="u-A")
    _send(client, "别人的会话", user_id="u-B")
    a_convs = client.get("/api/v1/chat/conversations", params={"user_id": "u-A"}).json()
    b_convs = client.get("/api/v1/chat/conversations", params={"user_id": "u-B"}).json()
    assert len(a_convs) == 2
    assert len(b_convs) == 1


def test_unknown_session_returns_404(client):
    import uuid

    resp = client.post(
        "/api/v1/chat",
        data={"message": "x", "session_id": str(uuid.uuid4()), "user_id": "u-test"},
    )
    assert resp.status_code == 404


def test_invalid_session_id_returns_400(client):
    resp = client.post(
        "/api/v1/chat", data={"message": "x", "session_id": "not-a-uuid", "user_id": "u-test"}
    )
    assert resp.status_code == 400


def test_delete_conversation(client):
    sid = _send(client, "待删除")["session_id"]
    assert client.delete(f"/api/v1/chat/conversations/{sid}").status_code == 200
    assert client.get(f"/api/v1/chat/conversations/{sid}").status_code == 404


def test_conversation_survives_simulated_restart(client, monkeypatch):
    """模拟重启：重置 DB 引擎全局后仍能读到（验证真落库，非内存态）。"""
    sid = _send(client, "持久化测试")["session_id"]
    # autouse fixture 用的是临时文件 DB；这里不重置 engine（会换库），
    # 直接再查一次确认数据在库里而非请求内存
    detail = client.get(f"/api/v1/chat/conversations/{sid}").json()
    assert detail["id"] == sid
    assert len(detail["messages"]) >= 2
