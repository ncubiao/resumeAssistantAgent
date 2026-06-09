"""向量检索服务（FAISS 封装）。

阶段 1 骨架：定义类结构与接口。
阶段 2 接入真实 FAISS 索引与向量库。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("vector_store")


class VectorStore:
    """FAISS 向量检索封装。"""

    def __init__(self, index_path: str | None = None, dim: int | None = None) -> None:
        self.index_path = index_path or settings.vector_index_path
        self.dim = dim or settings.vector_dim
        self._index = None
        self._metadata: list[dict] = []

    # ---------- 基础接口 ----------

    def _ensure_index(self):
        if self._index is not None:
            return self._index
        try:
            import faiss  # type: ignore

            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            if Path(self.index_path).exists():
                self._index = faiss.read_index(self.index_path)
                logger.info("faiss index loaded", path=self.index_path)
            else:
                self._index = faiss.IndexFlatL2(self.dim)
                logger.info("faiss index created", dim=self.dim)
        except Exception as exc:  # noqa: BLE001
            logger.warning("faiss not available, running in stub mode", error=str(exc))
            self._index = None
        return self._index

    def add(self, vectors: np.ndarray, metadata: list[dict]) -> None:
        """批量添加向量。"""
        idx = self._ensure_index()
        if idx is None:
            # 无 FAISS 时仅存 metadata 用于测试
            self._metadata.extend(metadata)
            return
        idx.add(vectors.astype("float32"))
        self._metadata.extend(metadata)

    def search(self, query_vector: np.ndarray, k: int = 5) -> list[dict]:
        """检索 Top-k。"""
        idx = self._ensure_index()
        if idx is None or len(self._metadata) == 0:
            return []
        scores, indices = idx.search(query_vector.reshape(1, -1).astype("float32"), k)
        results = []
        for score, i in zip(scores[0], indices[0]):
            if 0 <= i < len(self._metadata):
                item = dict(self._metadata[i])
                item["score"] = float(score)
                results.append(item)
        return results

    def save(self) -> None:
        idx = self._ensure_index()
        if idx is None:
            return
        try:
            import faiss  # type: ignore

            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(idx, self.index_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("faiss save failed", error=str(exc))

    def size(self) -> int:
        return len(self._metadata)
