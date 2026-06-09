"""LLM 客户端封装。

阶段 1：提供统一接口，支持 OpenAI / DeepSeek 风格的 API。
阶段 3+：在 Agent 节点中被调用。
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("llm_client")


class LLMClient:
    """统一的 LLM 调用封装。"""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client = None

    # ---------- 懒加载 ----------

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key or self.api_key.startswith("sk-your-"):
            logger.warning("LLM API key not configured - stub mode")
            self._client = False
            return self._client
        try:
            from langchain_openai import ChatOpenAI  # type: ignore

            self._client = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            logger.info("LLM client initialized", provider=self.provider, model=self.model)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM client init failed", error=str(exc))
            self._client = False
        return self._client

    # ---------- 公共接口 ----------

    @property
    def available(self) -> bool:
        """是否已接入 LLM。"""
        return bool(self._ensure_client())

    def invoke(self, prompt: str, system: str | None = None) -> str:
        """调用 LLM。未配置时返回空串，上层需处理。"""
        client = self._ensure_client()
        if not client:
            logger.warning("LLM invoke skipped: no client")
            return ""
        try:
            messages = []
            if system:
                from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore

                messages.append(SystemMessage(content=system))
                messages.append(HumanMessage(content=prompt))
            else:
                from langchain_core.messages import HumanMessage  # type: ignore

                messages.append(HumanMessage(content=prompt))
            response = client.invoke(messages)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM invoke failed", error=str(exc))
            return ""


# 全局单例
llm_client = LLMClient()
