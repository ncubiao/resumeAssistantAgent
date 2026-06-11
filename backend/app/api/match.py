"""岗位匹配相关 API 路由。

直接调用 ``match_tools.match_resume_to_jd``，从 DB 读简历 raw_text。
不绕 LangGraph：单功能调用走 tool 更直接、性能更好；图编排留给 ``/agent/analyze``。
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.tools.match_tools import match_resume_to_jd
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.schemas import (
    BatchMatchRequest,
    BatchMatchResultOut,
    MatchBreakdown,
    MatchRequest,
    MatchResultOut,
)
from app.services import resume_repository as repo

logger = get_logger("api.match")
router = APIRouter()


@router.post("/single", response_model=MatchResultOut, summary="单份简历 vs JD 匹配")
async def match_single(
    payload: MatchRequest, db: Session = Depends(get_db)
) -> MatchResultOut:
    raw_text = _load_resume_text(db, payload.resume_id)
    return _do_match(payload.resume_id, raw_text, payload.jd)


@router.post(
    "/batch",
    response_model=BatchMatchResultOut,
    summary="多份简历批量匹配 & 排序",
)
async def match_batch(
    payload: BatchMatchRequest, db: Session = Depends(get_db)
) -> BatchMatchResultOut:
    if not payload.resume_ids:
        raise HTTPException(status_code=400, detail="resume_ids 不能为空")
    if not payload.jd or not payload.jd.strip():
        raise HTTPException(status_code=400, detail="jd 不能为空")

    results: list[MatchResultOut] = []
    # 串行调用：N 份简历各发一次 LLM。生产场景可用 asyncio.gather 并发。
    for rid in payload.resume_ids:
        try:
            raw_text = _load_resume_text(db, rid)
        except HTTPException as exc:
            logger.warning("batch match: skip resume", resume_id=rid, status=exc.status_code)
            continue
        results.append(_do_match(rid, raw_text, payload.jd))

    results.sort(key=lambda r: r.overall_score, reverse=True)
    return BatchMatchResultOut(jd=payload.jd, results=results)


# ---------------- 内部 helper ----------------

def _load_resume_text(db: Session, resume_id: str) -> str:
    try:
        rid = UUID(resume_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"无效的简历 ID: {resume_id}") from None
    orm = repo.get_by_id(db, rid)
    if orm is None:
        raise HTTPException(status_code=404, detail=f"简历不存在: {resume_id}")
    return orm.raw_text or ""


def _do_match(resume_id: str, resume_text: str, jd_text: str) -> MatchResultOut:
    raw = match_resume_to_jd(resume_text, jd_text)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    try:
        score = float(data.get("overall_score") or 0)
    except (TypeError, ValueError):
        score = 0.0

    strengths = [str(s) for s in (data.get("strengths") or [])]
    gaps = [str(g) for g in (data.get("gaps") or [])]

    return MatchResultOut(
        resume_id=resume_id,
        overall_score=score,
        breakdown=MatchBreakdown(),  # tool 暂未输出拆解
        strengths=strengths,
        gaps=gaps,
    )
