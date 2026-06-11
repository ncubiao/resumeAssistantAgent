"""向量检索服务（FAISS 封装）。

阶段 2：接入真实 FAISS 索引，并修复 metadata 持久化。

设计要点：
- 维度单一事实来源为 ``settings.embedding_dim``（不再用旧的 vector_dim）。
- metadata 用 sidecar JSON（``<index>.meta.json``）与 FAISS 索引同步存盘，
  修掉"重启后 index 与内存 metadata 对不上"的问题。metadata 只存 ``resume_id``，
  详情回 DB 查。（多实例 / 生产场景更适合把 metadata 入库 + rowid 映射，此处单机务实。）
- 加载索引时校验维度，不匹配则告警并重建（换 provider/model 后维度会变）。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("vector_store")


class VectorStore:
    """FAISS 向量检索封装。"""

    def __init__(self, index_path: str | None = None, dim: int | None = None) -> None:
        self.index_path = index_path or settings.vector_index_path
        self.dim = dim or settings.embedding_dim
        self._meta_path = self.index_path + ".meta.json"
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
                index = faiss.read_index(self.index_path)
                # 维度校验：换 provider/model 后旧索引维度可能与当前 dim 不符
                if index.d != self.dim:
                    logger.warning(
                        "faiss index dim mismatch, rebuilding",
                        index_dim=index.d,
                        expected_dim=self.dim,
                    )
                    self._index = faiss.IndexFlatL2(self.dim)
                    self._metadata = []
                else:
                    self._index = index
                    self._metadata = self._load_metadata()
                    logger.info(
                        "faiss index loaded",
                        path=self.index_path,
                        size=len(self._metadata),
                    )
            else:
                self._index = faiss.IndexFlatL2(self.dim)
                logger.info("faiss index created", dim=self.dim)
        except Exception as exc:  # noqa: BLE001
            logger.warning("faiss not available, running in stub mode", error=str(exc))
            self._index = None
        return self._index

    def _load_metadata(self) -> list[dict]:
        try:
            if Path(self._meta_path).exists():
                with open(self._meta_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception as exc:  # noqa: BLE001
            logger.warning("faiss metadata load failed", error=str(exc))
        return []

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
            # metadata sidecar 必须与 index 同步写盘，否则重启后错位
            with open(self._meta_path, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            logger.error("faiss save failed", error=str(exc))

    def size(self) -> int:
        return len(self._metadata)

    def reset(self) -> None:
        """清空内存状态（测试用）。"""
        self._index = None
        self._metadata = []


# 全局单例（与 llm_client / embedding_client 风格一致）
vector_store = VectorStore()

__all__ = ["VectorStore", "vector_store"]
