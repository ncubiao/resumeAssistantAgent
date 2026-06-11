"""LangGraph Agent 编排端点。

阶段 3 的 demo 主舞台：一次请求执行 parser -> analyzer -> matcher/optimizer
完整流程，并返回每个节点的 trace（耗时、输出键、错误）。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.graph import run_analysis
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.schemas import (
    AgentAnalyzeRequest,
    AgentAnalyzeResponse,
    AnalysisDetail,
    MatchDetail,
    OptimizeDetail,
    OptimizeSuggestion,
    TraceEntry,
)
from app.services import resume_repository as repo

logger = get_logger("api.agent")
router = APIRouter()


@router.post(
    "/analyze",
    response_model=AgentAnalyzeResponse,
    summary="LangGraph 多 Agent 编排：parser → analyzer → matcher/optimizer",
)
async def analyze(
    payload: AgentAnalyzeRequest, db: Session = Depends(get_db)
) -> AgentAnalyzeResponse:
    """执行完整 Agent 工作流。

    `resume_id` 和 `raw_text` 二选一：
    - 给 `resume_id` 时从 DB 读简历原文；
    - 否则使用 `raw_text` 直接分析（不入库）。

    `mode` 控制下游分支：
    - "match"：只跑 matcher（需 jd）
    - "optimize"：只跑 optimizer
    - "both"：先 matcher 再 optimizer（需 jd）
    - 留空：jd 存在 → match，否则 → optimize
    """
    raw_text = _resolve_raw_text(payload, db)

    final = run_analysis(
        raw_text=raw_text,
        jd=payload.jd,
        mode=payload.mode,
        thread_id=payload.thread_id,
    )

    mode = final.get("mode") or ""
    return AgentAnalyzeResponse(
        parsed_resume=final.get("parsed_resume"),
        parse_confidence=float(final.get("parse_confidence") or 0.0),
        analysis=AnalysisDetail(
            skills=list(final.get("skills") or []),
            highlights=list(final.get("highlights") or []),
            weaknesses=list(final.get("weaknesses") or []),
            education_score=int(final.get("education_score") or 0),
            experience_score=int(final.get("experience_score") or 0),
        ),
        match=_extract_match(final) if mode in {"match", "both"} else None,
        optimize=_extract_optimize(final) if mode in {"optimize", "both"} else None,
        trace=[TraceEntry(**t) for t in (final.get("trace") or [])],
        thread_id=str(final.get("thread_id") or ""),
        mode=mode,
    )


def _resolve_raw_text(payload: AgentAnalyzeRequest, db: Session) -> str:
    if payload.resume_id:
        try:
            rid = UUID(payload.resume_id)
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(status_code=400, detail="无效的简历 ID（应为 UUID）") from None
        orm = repo.get_by_id(db, rid)
        if orm is None:
            raise HTTPException(status_code=404, detail="简历不存在")
        return orm.raw_text or ""
    raw = (payload.raw_text or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="resume_id 与 raw_text 至少提供一项")
    return raw


def _extract_match(state: dict) -> MatchDetail:
    return MatchDetail(
        score=float(state.get("match_score") or 0.0),
        strengths=list(state.get("match_strengths") or []),
        gaps=list(state.get("match_gaps") or []),
        reasoning=str(state.get("match_reasoning") or ""),
    )


def _extract_optimize(state: dict) -> OptimizeDetail:
    raw_suggestions = state.get("optimize_suggestions") or []
    suggestions: list[OptimizeSuggestion] = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue
        suggestions.append(
            OptimizeSuggestion(
                category=str(item.get("category") or "其他"),
                original=str(item.get("original") or ""),
                improved=str(item.get("improved") or ""),
                reason=str(item.get("reason") or ""),
            )
        )
    return OptimizeDetail(suggestions=suggestions)
