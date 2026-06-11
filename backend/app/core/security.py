"""API Key 鉴权。

设计选择：轻量的 ``X-API-Key`` 头校验，而非 JWT/OAuth。理由：
- 作品集 / 单租户场景，API Key 足够，复杂度低；
- 通过 ``settings.auth_enabled`` 开关控制——默认关闭，本地开发与 demo 无需带 key，
  与项目一贯的"优雅降级"风格一致；生产置 true 即可强制鉴权。

用法：在 include_router 时挂为路由级依赖：
    app.include_router(r, dependencies=[Depends(require_api_key)])
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("security")

_API_KEY_HEADER = "X-API-Key"


async def require_api_key(x_api_key: str | None = Header(default=None, alias=_API_KEY_HEADER)) -> None:
    """校验 ``X-API-Key`` 请求头。

    - auth_enabled=False：直接放行（默认）。
    - auth_enabled=True 且未配置任何 key：放行但告警（配置疏漏保护，不锁死服务）。
    - 否则：key 必须命中 settings.api_key_set，否则 401。
    """
    if not settings.auth_enabled:
        return

    valid_keys = settings.api_key_set
    if not valid_keys:
        logger.warning("auth enabled but no api_keys configured; allowing request")
        return

    if x_api_key and x_api_key in valid_keys:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或缺失的 API Key",
        headers={"WWW-Authenticate": _API_KEY_HEADER},
    )


__all__ = ["require_api_key"]
