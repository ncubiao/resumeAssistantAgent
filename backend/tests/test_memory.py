"""阶段 7：长期语义记忆（C）测试。

抽取依赖 LLM（mock 之），存/召回的去重与兜底走离线路径。
"""
from __future__ import annotations

import pytest

from app.services import memory_service


@pytest.fixture
def db_session():
    """直接拿一个测试 DB session（_isolated_db autouse 已建表）。"""
    from app.core import database

    session = database._get_session_local()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # 默认关掉 embedding，记忆走时间序兜底
    monkeypatch.setattr(memory_service.embedding_client, "_unavailable", True)
    # 每个测试用独立的内存索引，避免串扰
    from app.services.vector_store import VectorStore

    monkeypatch.setattr(memory_service, "memory_store", VectorStore(index_path="/tmp/nonexist.bin"))


# ---------------- 抽取 ----------------

def test_extract_returns_empty_when_llm_unavailable(monkeypatch):
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", True)
    assert memory_service.extract_memories("我想做后端", "好的", "candidate") == []


def test_extract_parses_llm_json(monkeypatch):
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", False)
    monkeypatch.setattr(llm_client, "_client", object())
    monkeypatch.setattr(
        llm_client,
        "invoke_json",
        lambda **kw: {"memories": [
            {"kind": "profile", "content": "目标岗位是 Python 后端"},
            {"kind": "fact", "content": "缺少 K8s 经验"},
        ]},
    )
    out = memory_service.extract_memories("我想做 Python 后端但不会 K8s", "建议补强容器化", "candidate")
    assert len(out) == 2
    assert out[0]["kind"] == "profile"
    assert "Python" in out[0]["content"]


def test_extract_normalizes_bad_kind(monkeypatch):
    from app.utils.llm_client import llm_client

    monkeypatch.setattr(llm_client, "_unavailable", False)
    monkeypatch.setattr(llm_client, "_client", object())
    monkeypatch.setattr(
        llm_client, "invoke_json", lambda **kw: {"memories": [{"kind": "weird", "content": "x"}]}
    )
    out = memory_service.extract_memories("a", "b", "recruiter")
    assert out[0]["kind"] == "fact"  # 非法 kind 归一化


# ---------------- 存储 + 召回 ----------------

def test_save_and_recall_fallback(db_session):
    memory_service.save_memories(
        db_session,
        user_id="u1",
        memories=[{"kind": "fact", "content": "喜欢远程办公"}],
        source_session="s1",
    )
    db_session.commit()
    recalled = memory_service.recall_memories(db_session, user_id="u1", query="工作方式")
    assert "喜欢远程办公" in recalled


def test_save_dedup(db_session):
    for _ in range(3):
        memory_service.save_memories(
            db_session, user_id="u2", memories=[{"kind": "fact", "content": "会 Python"}]
        )
    db_session.commit()
    mems = memory_service.list_memories_by_user(db_session, "u2")
    assert len(mems) == 1  # 去重，只存一条


def test_recall_isolates_by_user(db_session):
    memory_service.save_memories(db_session, user_id="ua", memories=[{"kind": "fact", "content": "A的秘密"}])
    memory_service.save_memories(db_session, user_id="ub", memories=[{"kind": "fact", "content": "B的秘密"}])
    db_session.commit()
    a = memory_service.recall_memories(db_session, user_id="ua", query="x")
    assert "A的秘密" in a
    assert "B的秘密" not in a  # 不串户


def test_recall_empty_when_no_memories(db_session):
    assert memory_service.recall_memories(db_session, user_id="nobody", query="x") == []


def test_memory_disabled_recall_returns_empty(db_session, monkeypatch):
    monkeypatch.setattr(memory_service.settings, "memory_enabled", False)
    memory_service.save_memories(db_session, user_id="u3", memories=[{"kind": "fact", "content": "x"}])
    db_session.commit()
    assert memory_service.recall_memories(db_session, user_id="u3", query="x") == []
