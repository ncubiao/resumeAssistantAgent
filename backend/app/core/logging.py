"""结构化日志配置。

优先使用 structlog；若不可用（最小依赖环境），退回到标准 logging。

阶段 5：新增敏感信息脱敏——日志中的邮箱 / 电话 / API Key 自动打码，
避免简历 PII 与密钥泄露到日志系统。
"""
from __future__ import annotations

import logging
import re
import sys

try:
    import structlog  # type: ignore

    _HAS_STRUCTLOG = True
except ImportError:
    structlog = None  # type: ignore
    _HAS_STRUCTLOG = False


# ---------- 敏感信息脱敏 ----------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{6,}\d)(?!\d)")
_APIKEY_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{2,})\b")


def mask_sensitive(value):
    """对单个值做脱敏（字符串直接处理，dict/list 递归）。"""
    if isinstance(value, str):
        s = _EMAIL_RE.sub("***@***", value)
        s = _APIKEY_RE.sub(lambda m: m.group(1)[:6] + "***", s)
        s = _PHONE_RE.sub("***", s)
        return s
    if isinstance(value, dict):
        return {k: mask_sensitive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(mask_sensitive(v) for v in value)
    return value


def _mask_processor(_logger, _method, event_dict):
    """structlog processor：对 event_dict 所有值脱敏。"""
    return {k: mask_sensitive(v) for k, v in event_dict.items()}


def setup_logging(log_level: str = "INFO") -> None:
    """初始化日志配置。

    Args:
        log_level: 日志级别，DEBUG / INFO / WARNING / ERROR
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    if _HAS_STRUCTLOG:
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=level,
        )
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                _mask_processor,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
            level=level,
        )


def get_logger(name: str = "resume_agent"):
    """获取一个命名 logger。

    在没有 structlog 时退化为标准 logging，支持 **kwargs 调用会被忽略。
    """
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)

    logger = logging.getLogger(name)

    # 封装一层，把所有调用把 **kwargs 忽略掉，保持与 structlog 调用一致的用法。
    class _FallbackLogger:
        def __init__(self, lg: logging.Logger) -> None:
            self._lg = lg

        def _fmt(self, msg: str, **kwargs: object) -> str:
            msg = mask_sensitive(msg)
            if kwargs:
                extras = " ".join(f"{k}={mask_sensitive(v)}" for k, v in kwargs.items())
                return f"{msg} | {extras}"
            return msg

        def debug(self, msg: str, **kwargs: object) -> None:
            self._lg.debug(self._fmt(msg, **kwargs))

        def info(self, msg: str, **kwargs: object) -> None:
            self._lg.info(self._fmt(msg, **kwargs))

        def warning(self, msg: str, **kwargs: object) -> None:
            self._lg.warning(self._fmt(msg, **kwargs))

        def warn(self, msg: str, **kwargs: object) -> None:
            self.warning(msg, **kwargs)

        def error(self, msg: str, **kwargs: object) -> None:
            self._lg.error(self._fmt(msg, **kwargs))

        def exception(self, msg: str, **kwargs: object) -> None:
            self._lg.exception(self._fmt(msg, **kwargs))

        def critical(self, msg: str, **kwargs: object) -> None:
            self._lg.critical(self._fmt(msg, **kwargs))

        def bind(self, **_kwargs: object) -> "_FallbackLogger":
            return self

    return _FallbackLogger(logger)
