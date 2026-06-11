"""Embedding（向量化）客户端封装。

与 ``llm_client`` 解耦：chat 与 embedding 是不同端点（``/embeddings``），
且 provider 能力矩阵不同（DeepSeek 无 embedding API）。独立成模块更内聚。

设计与 ``llm_client`` 对齐：
  1. 懒加载 + 单例
  2. 未配置 / provider 无 embedding 能力时 ``available=False``，调用返回 None 不抛异常
     —— 上层据此降级为关键词检索，与 parser_agent 的 heuristic fallback 风格一致
  3. 走 OpenAI 兼容的 ``POST {base_url}/embeddings`` 协议（httpx），支持 ``dimensions`` 参数
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("embedding")

# 各 provider 的 embedding 能力推断表。
# 值为 None 表示该 provider 没有 embedding 端点（如 DeepSeek）。
_PROVIDER_DEFAULTS: dict[str, dict[str, Any] | None] = {
    "dashscope": {
        "model": "text-embedding-v3",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "dim": 1024,
    },
    "openai": {
        "model": "text-embedding-3-small",
        "base_url": "https://api.openai.com/v1",
        "dim": 1536,
    },
    "deepseek": None,  # 无 embedding API
}


class EmbeddingClient:
    """统一的向量化封装。"""

    def __init__(self) -> None:
        self._max_retries = 2
        self._retry_backoff = 1.0
        self._unavailable: bool | None = None  # None=未判定
        self._resolved: dict[str, Any] | None = None

    # ---------------- 配置解析 ----------------

    def _resolve(self) -> dict[str, Any] | None:
        """解析最终生效的 (provider, model, api_key, base_url, dim)。

        留空项的回退规则见 config.py。provider 无 embedding 能力时返回 None。
        """
        if self._resolved is not None:
            return self._resolved

        provider = (settings.embedding_provider or settings.llm_provider or "openai").lower().strip()
        defaults = _PROVIDER_DEFAULTS.get(provider)
        if defaults is None:
            logger.info("embedding provider has no embedding endpoint", provider=provider)
            return None

        api_key = settings.embedding_api_key or settings.llm_api_key or ""
        model = settings.embedding_model or defaults["model"]
        base_url = settings.embedding_base_url or defaults["base_url"]
        # 维度单一事实来源：显式配置优先，否则用 provider 默认
        dim = int(settings.embedding_dim or defaults["dim"])

        self._resolved = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url.rstrip("/"),
            "dim": dim,
        }
        return self._resolved

    @staticmethod
    def _key_ok(api_key: str) -> bool:
        """与 llm_client 一致的占位符检查。"""
        if not api_key:
            return False
        low = api_key.lower()
        if "你的" in api_key or "your" in low:
            return False
        if api_key.strip() in {"sk-", "sk-proj-", "sk-proj-你的xxx"}:
            return False
        return len(api_key.strip()) >= 8

    # ---------------- 公共属性 ----------------

    @property
    def available(self) -> bool:
        if self._unavailable is True:
            return False
        cfg = self._resolve()
        if cfg is None or not self._key_ok(cfg["api_key"]):
            self._unavailable = True
            return False
        return True

    @property
    def dim(self) -> int:
        cfg = self._resolve()
        return cfg["dim"] if cfg else int(settings.embedding_dim or 1024)

    # ---------------- 公共方法 ----------------

    def embed_texts(self, texts: list[str]) -> np.ndarray | None:
        """批量向量化。返回 (n, dim) float32，不可用 / 失败时返回 None。"""
        if not self.available or not texts:
            return None
        cfg = self._resolve()
        assert cfg is not None

        import httpx

        body = {"model": cfg["model"], "input": texts, "dimensions": cfg["dim"]}
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        url = f"{cfg['base_url']}/embeddings"

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=60)
                resp.raise_for_status()
                data = resp.json().get("data") or []
                if not data:
                    return None
                # 关键：按返回的 index 排序，不假设顺序 == 输入顺序
                data_sorted = sorted(data, key=lambda d: d.get("index", 0))
                vectors = np.array(
                    [d["embedding"] for d in data_sorted], dtype="float32"
                )
                return vectors
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("embedding call failed", attempt=attempt + 1, error=str(exc))
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff * (2**attempt))
        if last_exc is not None:
            logger.error("embedding call finally failed", error=str(last_exc))
        return None

    def embed_query(self, text: str) -> np.ndarray | None:
        """单条向量化，返回 (dim,) float32 或 None。"""
        vectors = self.embed_texts([text])
        if vectors is None or len(vectors) == 0:
            return None
        return vectors[0]

    def reset(self) -> None:
        """重置缓存状态，主要给测试用（切换配置后调用）。"""
        self._unavailable = None
        self._resolved = None


# 全局单例
embedding_client = EmbeddingClient()

__all__ = ["EmbeddingClient", "embedding_client"]
