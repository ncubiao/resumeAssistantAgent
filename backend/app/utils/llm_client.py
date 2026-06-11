"""LLM 客户端封装。

统一管理 LLM 调用，支持多家服务商（OpenAI 兼容协议）：
  - dashscope (阿里云 DashScope / Qwen / 通义千问)
  - openai
  - deepseek
  - 其它任何实现了 OpenAI Chat Completions 协议的服务商

核心功能：
  1. 懒加载 + 单例
  2. 支持 system / user message
  3. 支持 ``response_format="json_object"`` 强制 JSON 输出（DashScope 兼容）
  4. 简单的指数退避重试
  5. 未配置 API Key 时自动进入 stub 模式，不抛异常，便于本地开发与测试

"""
from __future__ import annotations

import json
import time
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("llm_client")


# ---------------- 辅助函数：从任意文本中提取 JSON ----------------
import re as _re


def _extract_json(text: str) -> Any | None:
    """从 LLM 文本输出中提取并解析 JSON 对象 / 数组。

    支持的典型情况：
    1. 纯 JSON：`{"a":1}`
    2. 代码块包裹：```json\n{...}\n```
    3. 文字中夹带 JSON："好的，结果是：\n{...}\n"
    4. JSON 数组：[...]
    """
    if not text:
        return None
    cleaned = text.strip()

    # 策略 1：直接解析
    try:
        return json.loads(cleaned)
    except Exception:  # noqa: BLE001
        pass

    # 策略 2：代码块形式 ```json ... ``` / ``` ... ```
    block_match = _re.search(
        r"```(?:json|JSON|js|javascript)?\s*\n?(.*?)```",
        cleaned,
        flags=_re.DOTALL,
    )
    if block_match:
        try:
            return json.loads(block_match.group(1).strip())
        except Exception:  # noqa: BLE001
            pass

    # 策略 3：找第一个 { 到最后一个 }，或第一个 [ 到最后一个 ]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = cleaned.find(open_c)
        end = cleaned.rfind(close_c)
        if 0 <= start < end:
            candidate = cleaned[start:end + 1]
            try:
                return json.loads(candidate)
            except Exception:  # noqa: BLE001
                # 3b：如果 { 和 } 可能有多个，尝试从每个配对
                # 找到第一个 { 和最后一个 } 之间的内容可能包含非 JSON 文本
                # 逐个尝试不同的子字符串
                pass

    # 策略 4：逐行扫描，拼接所有看起来像 JSON 的行 / 每行分别尝试
    lines = cleaned.split("\n")
    # 优先尝试每一行、以及多行块
    candidate_lines = []
    for line in lines:
        candidate_lines.append(line)
        joined = "\n".join(candidate_lines[-30:])
        try:
            return json.loads(joined.strip())
        except Exception:  # noqa: BLE001
            continue

    return None

# 各服务商默认的 base_url（当用户未显式设置时使用）
_DEFAULT_BASE_URLS: dict[str, str] = {
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

# 各服务商常见模型名称（仅用于日志，不参与逻辑）
_COMMON_MODELS: dict[str, list[str]] = {
    "dashscope": [
        "qwen3-vl-plus",
        "qwen3-coder-plus",
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
        "deepseek-v3",
    ],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
}


class LLMClient:
    """统一的 LLM 调用封装（基于 langchain-openai 的 ChatOpenAI）。

    所有通过 OpenAI 兼容协议暴露的服务都可以用它调用，只需正确配置：

    - LLM_PROVIDER
    - LLM_API_KEY
    - LLM_MODEL
    - LLM_BASE_URL (如果 provider 在 _DEFAULT_BASE_URLS 中可以省略)
    """

    def __init__(self) -> None:
        self.provider: str = (settings.llm_provider or "openai").lower().strip()
        self.api_key: str = settings.llm_api_key or ""
        self.model: str = settings.llm_model or ""
        # 未显式写 base_url 时，用该 provider 的默认值
        self.base_url: str = settings.llm_base_url or _DEFAULT_BASE_URLS.get(
            self.provider, "https://api.openai.com/v1"
        )
        self.temperature: float = float(getattr(settings, "llm_temperature", 0.2) or 0.2)
        self.max_tokens: int = int(getattr(settings, "llm_max_tokens", 2048) or 2048)

        self._max_retries: int = 2
        self._retry_backoff: float = 1.0

        self._client: Any = None
        # 懒加载过程中是否已经明确 "不可用"（例如缺少 key 或依赖）
        self._unavailable: bool = False

    # ---------------- 公共属性 ----------------

    @property
    def available(self) -> bool:
        """是否已配置并初始化成功。"""
        return bool(self._ensure_client())

    @property
    def display_name(self) -> str:
        """便于日志 / UI 展示的名字。"""
        return f"{self.provider}:{self.model}"

    # ---------------- 初始化 ----------------

    def _is_configured(self) -> bool:
        if not self.api_key:
            return False
        # 形如 "sk-你的xxx" 明显是占位
        if "你的" in self.api_key or "your" in self.api_key.lower():
            return False
        # 只有 "sk-" 没填后面的具体内容
        if self.api_key.strip() in {"sk-", "sk-proj-", "sk-proj-你的xxx"}:
            return False
        # 至少要大于 8 个字符
        if len(self.api_key.strip()) < 8:
            return False
        return True

    def _ensure_client(self) -> Any:
        """懒加载 ChatOpenAI 客户端；失败或未配置时返回 False。"""
        if self._client is not None:
            return self._client
        if self._unavailable:
            return False
        if not self._is_configured():
            logger.warning(
                "LLM API key not configured or looks like placeholder - running in stub mode",
                provider=self.provider,
                model=self.model,
                key_preview=(self.api_key[:8] + "...") if self.api_key else "(empty)",
            )
            self._unavailable = True
            return False
        try:
            from langchain_openai import ChatOpenAI  # type: ignore

            # 为 DashScope 做一些默认参数适配：
            # DashScope 的 ChatOpenAI 兼容模式不依赖超时等参数，照常传即可。
            self._client = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=60,
                max_retries=self._max_retries,
            )
            logger.info(
                "LLM client initialized",
                provider=self.provider,
                model=self.model,
                base_url=self.base_url,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM client init failed", error=str(exc), provider=self.provider)
            self._unavailable = True
            return False
        return self._client

    # ---------------- 辅助 ----------------

    @staticmethod
    def _build_messages(
        prompt: str, system: str | None = None, history: list[dict[str, str]] | None = None
    ) -> list[Any]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # type: ignore

        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        if history:
            for msg in history:
                role = (msg.get("role") or "").lower()
                content = msg.get("content") or ""
                if role == "assistant":
                    messages.append(AIMessage(content=content))
                elif role in {"human", "user"}:
                    messages.append(HumanMessage(content=content))
        messages.append(HumanMessage(content=prompt))
        return messages

    def _call(self, messages: list[Any], expect_json: bool = False) -> str:
        """真正发起调用，带简单重试。"""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                kwargs: dict[str, Any] = {}
                if expect_json:
                    # DashScope / Qwen / OpenAI 官方支持 response_format=json_object。
                    # 注意：response_format 要作为 invoke 的运行时 kwarg 直接透传给底层
                    # Completions.create()；不能用 model_kwargs 包裹（那是 ChatOpenAI 的
                    # 构造参数，透传到 create() 会报 unexpected keyword argument）。
                    kwargs["response_format"] = {"type": "json_object"}
                response = self._client.invoke(messages, **kwargs)
                content = getattr(response, "content", None)
                if content is None:
                    content = str(response)
                return content.strip() if isinstance(content, str) else str(content).strip()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "LLM call failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff * (2**attempt))
        if last_exc is not None:
            logger.error("LLM call finally failed", error=str(last_exc))
        return ""

    # ---------------- 公共方法 ----------------

    def invoke(
        self,
        prompt: str,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        expect_json: bool = False,
    ) -> str:
        """发起一次文本对话，返回 LLM 的纯文本回答。"""
        client = self._ensure_client()
        if not client:
            logger.warning("LLM invoke skipped: client not available", provider=self.provider)
            return ""

        messages = self._build_messages(prompt, system=system, history=history)
        return self._call(messages, expect_json=expect_json)

    def invoke_vision(
        self,
        image_bytes: bytes,
        image_format: str,
        prompt: str,
        system: str | None = None,
    ) -> str:
        """调用视觉模型，输入一张图片 + 一段提示，返回文本回答。

        Args:
            image_bytes: 图片原始字节
            image_format: "png" / "jpg" / "jpeg" / "webp" / "bmp" / "gif"
            prompt: 向 LLM 提问的文本，例如 "请提取图片中的所有文字"
            system: 可选 system message
        """
        client = self._ensure_client()
        if not client:
            logger.warning("LLM invoke_vision skipped: client not available")
            return ""

        # 走 requests 直接构造多模态请求（langchain ChatOpenAI 对 image_url 内容形式的兼容在各版本不一致，
        # 这里直接构造符合 DashScope/OpenAI Chat Completions 协议的消息，更稳）
        import base64

        import requests

        b64 = base64.b64encode(image_bytes).decode("ascii")
        fmt = "jpeg" if image_format.lower() in {"jpg", "jpeg"} else image_format.lower()
        image_url = f"data:image/{fmt};base64,{b64}"

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        )

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                r = requests.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=120,
                )
                r.raise_for_status()
                data = r.json()
                choices = data.get("choices") or []
                if not choices:
                    return ""
                msg = choices[0].get("message") or {}
                content = msg.get("content") or ""
                logger.info(
                    "LLM vision call finished",
                    provider=self.provider,
                    model=self.model,
                    chars=len(content),
                    attempt=attempt + 1,
                )
                return str(content).strip()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "LLM vision call failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff * (2**attempt))
        if last_exc is not None:
            logger.error("LLM vision call finally failed", error=str(last_exc))
        return ""

    def invoke_json(
        self,
        prompt: str,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        default: Any = None,
    ) -> dict[str, Any] | list[Any]:
        """调用并期望返回 JSON。失败时返回 default（默认 {}）。

        相比普通 invoke：额外支持多种 JSON 提取策略（markdown 代码块、
        文本中提取第一个 {...} / [...] 对象等），以应对不同模型的输出习惯。
        """
        text = self.invoke(prompt, system=system, history=history, expect_json=True)
        if not text:
            return default if default is not None else {}

        parsed = _extract_json(text)
        if parsed is not None:
            return parsed

        logger.warning("LLM JSON parse failed after all strategies", snippet=text[:300])
        return default if default is not None else {}

    # ---------------- 便捷方法（供单元测试 mock） ----------------

    def reset(self) -> None:
        """重置状态。主要给测试用。"""
        self._client = None
        self._unavailable = False


# 全局单例
llm_client = LLMClient()

__all__ = ["LLMClient", "llm_client"]
