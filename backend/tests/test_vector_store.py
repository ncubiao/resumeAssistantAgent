"""向量存储服务测试（stub 模式）。"""
from __future__ import annotations

import numpy as np

from app.services.vector_store import VectorStore


def test_vector_store_stub_add_and_size(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.vector_store.settings.vector_index_path",
        str(tmp_path / "test.bin"),
    )
    vs = VectorStore(index_path=str(tmp_path / "test.bin"), dim=4)
    vs.add(
        np.random.rand(3, 4).astype("float32"),
        [{"resume_id": f"r{i}"} for i in range(3)],
    )
    assert vs.size() == 3


def test_vector_store_search_no_data(tmp_path):
    vs = VectorStore(index_path=str(tmp_path / "empty.bin"), dim=4)
    results = vs.search(np.random.rand(4).astype("float32"), k=3)
    assert isinstance(results, list)
