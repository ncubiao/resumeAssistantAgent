"""FastAPI 应用入口 - resumeAssistantAgent 后端。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api import agent, chat, match, optimize, resume
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import get_logger, setup_logging
from app.core.metrics import metrics
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.core.security import require_api_key
from app.utils.llm_client import llm_client

# 初始化日志
setup_logging(settings.log_level)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表（create_all 幂等，已存在则跳过）。

    阶段 2 起数据库正式启用。生产化时建议切换为 Alembic 迁移管理。
    """
    init_db()
    logger.info(
        "application startup complete",
        env=settings.app_env,
        auth_enabled=settings.auth_enabled,
        rate_limit=settings.rate_limit_enabled,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description="简历分析 AI Agent 后端 API（支持 DashScope / OpenAI 兼容模式）",
    version="0.3.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# ---------- 中间件（顺序：先注册的更靠外层）----------
# RequestContext 最外层：保证限流响应也带 request_id 与访问日志。
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)

# CORS：从配置读取允许来源，不再用通配 "*"。
_cors_origins = settings.cors_origins_list or ["*"]
_allow_credentials = "*" not in _cors_origins  # 通配时浏览器规范禁止携带凭证
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 统一异常信封 ----------

@app.exception_handler(HTTPException)
async def _http_exc_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail, "request_id": request_id}},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def _unhandled_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    logger.error("unhandled exception", path=request.url.path, error=str(exc), request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": "服务器内部错误", "request_id": request_id}},
    )


# ---------- 路由（业务路由统一挂 API Key 鉴权依赖）----------
_secured = [Depends(require_api_key)]
app.include_router(resume.router, prefix="/api/v1/resumes", tags=["resumes"], dependencies=_secured)
app.include_router(match.router, prefix="/api/v1/matches", tags=["matches"], dependencies=_secured)
app.include_router(optimize.router, prefix="/api/v1/optimize", tags=["optimize"], dependencies=_secured)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"], dependencies=_secured)
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"], dependencies=_secured)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """服务健康检查（浅层，永远快速返回）。"""
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
    }


@app.get("/health/deep", tags=["health"])
async def health_deep() -> JSONResponse:
    """深度健康检查：探测 DB / 向量库 / LLM 配置，任一关键依赖故障返回 503。"""
    checks: dict[str, dict] = {}

    # DB：执行一次 SELECT 1
    try:
        from sqlalchemy import text

        from app.core.database import session_scope

        with session_scope() as s:
            s.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"status": "error", "detail": str(exc)[:200]}

    # 向量库：报告可用性与规模（不可用不算致命，会降级到关键词检索）
    try:
        from app.services.embedding import embedding_client
        from app.services.vector_store import vector_store

        checks["vector_store"] = {
            "status": "ok",
            "embedding_available": embedding_client.available,
            "indexed": vector_store.size(),
        }
    except Exception as exc:  # noqa: BLE001
        checks["vector_store"] = {"status": "error", "detail": str(exc)[:200]}

    # LLM：仅报告配置状态（不实际调用），未配置不算致命（有 heuristic 兜底）
    checks["llm"] = {"status": "ok", "available": llm_client.available, "provider": llm_client.provider}

    # 只有 DB 故障才判定整体不健康
    healthy = checks["database"]["status"] == "ok"
    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


@app.get("/metrics", tags=["metrics"], response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    """Prometheus 文本格式指标暴露。"""
    return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/api/v1/llm/health", tags=["llm"])
async def llm_health_check() -> dict:
    """LLM 连通性检查。

    该接口不真正调用模型，只报告：
    - 当前配置的 provider / model / base_url
    - api_key 是否已配置（不回传 key 本身）
    - 依赖是否可导入
    """
    key = settings.llm_api_key or ""
    key_masked = key[:8] + "***" if len(key) > 8 else "(empty)"
    return {
        "provider": llm_client.provider,
        "model": llm_client.model,
        "base_url": llm_client.base_url,
        "api_key_configured": bool(key),
        "api_key_preview": key_masked,
        "api_key_passes_check": (
            bool(key)
            and "你的" not in key
            and "your" not in key.lower()
            and key.strip() not in {"sk-", "sk-proj-", "sk-proj-你的xxx"}
            and len(key.strip()) >= 8
        ),
        "client_available": llm_client.available,
        "note": (
            "如果 api_key_passes_check=false，请检查 .env 文件中 LLM_API_KEY。"
            " 如果 client_available=false，说明 key 被判定为占位符或未配置，模型会走 fallback。"
        ),
    }


@app.post("/api/v1/llm/test", tags=["llm"])
async def llm_test(payload: dict | None = None) -> dict:
    """真正发起一次 LLM 调用，用于验证配置。

    可通过 JSON body 传入自定义 prompt：
        {"prompt": "请用一句话介绍你自己"}
    """
    prompt = (payload or {}).get("prompt") or "你好，请用一句话介绍你自己。"
    reply = llm_client.invoke(prompt)
    return {
        "provider": llm_client.provider,
        "model": llm_client.model,
        "prompt": prompt,
        "reply": reply or "(empty - LLM 未配置 / 调用失败)",
        "ok": bool(reply),
    }


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "message": "resumeAssistantAgent API",
        "docs": "/docs",
        "health": "/health",
        "llm_health": "/api/v1/llm/health",
        "supported_providers": ["dashscope", "openai", "deepseek"],
    }
