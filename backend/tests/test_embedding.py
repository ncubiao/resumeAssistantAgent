"""Embedding 客户端测试。

默认在无 / 占位 key 环境下验证降级行为；真实 key 下也不应抛异常。
"""
from __future__ import annotations

import numpy as np

from app.services.embedding import EmbeddingClient


def test_no_embedding_when_provider_is_deepseek(monkeypatch):
    """DeepSeek 无 embedding 端点 -> available=False，embed 返回 None。"""
    from app.services import embedding as emb

    monkeypatch.setattr(emb.settings, "embedding_provider", "deepseek")
    monkeypatch.setattr(emb.settings, "llm_provider", "deepseek")
    client = EmbeddingClient()
    assert client.available is False
    assert client.embed_query("hello") is None
    assert client.embed_texts(["a", "b"]) is None


def test_no_embedding_when_key_missing(monkeypatch):
    from app.services import embedding as emb

    monkeypatch.setattr(emb.settings, "embedding_provider", "dashscope")
    monkeypatch.setattr(emb.settings, "embedding_api_key", "")
    monkeypatch.setattr(emb.settings, "llm_api_key", "你的key")  # 占位符
    client = EmbeddingClient()
    assert client.available is False
    assert client.embed_query("hello") is None


def test_dim_resolution(monkeypatch):
    from app.services import embedding as emb

    monkeypatch.setattr(emb.settings, "embedding_provider", "openai")
    monkeypatch.setattr(emb.settings, "embedding_dim", 1536)
    client = EmbeddingClient()
    assert client.dim == 1536


def test_embed_parses_and_orders_response(monkeypatch):
    """mock httpx，验证按 index 排序、返回 (n, dim) float32。"""
    from app.services import embedding as emb

    monkeypatch.setattr(emb.settings, "embedding_provider", "openai")
    monkeypatch.setattr(emb.settings, "embedding_api_key", "sk-test-1234567890")
    monkeypatch.setattr(emb.settings, "embedding_dim", 3)

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            # 故意乱序返回，验证客户端会按 index 重排
            return {"data": [
                {"index": 1, "embedding": [1.0, 1.0, 1.0]},
                {"index": 0, "embedding": [0.0, 0.0, 0.0]},
            ]}

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())

    client = EmbeddingClient()
    vecs = client.embed_texts(["a", "b"])
    assert isinstance(vecs, np.ndarray)
    assert vecs.shape == (2, 3)
    assert vecs.dtype == np.float32
    # index 0 应排在前
    assert vecs[0].tolist() == [0.0, 0.0, 0.0]
    assert vecs[1].tolist() == [1.0, 1.0, 1.0]
