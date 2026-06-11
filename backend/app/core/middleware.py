"""自定义中间件：请求上下文（request_id + 访问日志）与限流。

- RequestContextMiddleware：为每个请求生成 request_id，绑定到 structlog contextvars
  （于是请求期间所有日志自动带 request_id），写入 ``request.state`` 供异常处理器读取，
  并在响应头返回 ``X-Request-ID``。记录一条访问日志（方法/路径/状态/耗时）。
- RateLimitMiddleware：内存滑动窗口限流，按客户端 IP。默认关闭，生产置
  ``settings.rate_limit_enabled=True``。超限返回 429 + Retry-After。
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("http")

# 限流豁免路径（健康检查 / 文档不计入）
_RATE_LIMIT_EXEMPT = {"/health", "/", "/docs", "/openapi.json", "/redoc"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex[:16]
        request.state.request_id = request_id

        # 绑定到 structlog 上下文，使本请求内所有日志自动携带 request_id
        try:
            import structlog  # type: ignore

            structlog.contextvars.bind_contextvars(request_id=request_id)
        except Exception:  # noqa: BLE001
            pass

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            try:
                import structlog  # type: ignore

                structlog.contextvars.unbind_contextvars("request_id")
            except Exception:  # noqa: BLE001
                pass

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按客户端 IP 的滑动窗口限流（60 秒窗口）。"""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        # 动态读 settings，便于测试 monkeypatch 开关
        if not settings.rate_limit_enabled or request.url.path in _RATE_LIMIT_EXEMPT:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = 60.0
        limit = max(1, settings.rate_limit_per_minute)

        bucket = self._hits[client_ip]
        # 移除窗口外的时间戳
        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = int(window - (now - bucket[0])) + 1
            request_id = getattr(request.state, "request_id", "")
            logger.warning("rate limit exceeded", client_ip=client_ip, limit=limit)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": 429,
                        "message": f"请求过于频繁，请 {retry_after}s 后重试",
                        "request_id": request_id,
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)


__all__ = ["RequestContextMiddleware", "RateLimitMiddleware"]
