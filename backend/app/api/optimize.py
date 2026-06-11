"""简历优化相关 API 路由。

- ``/suggestions``：基于简历（+可选目标 JD）生成结构化优化建议（复用 optimize_tools）。
- ``/rewrite``：对单段文本做润色重写（直接走 LLM，无需独立 tool）。
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.tools.optimize_tools import generate_optimize_suggestions
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.schemas import (
    OptimizeRequest,
    OptimizeResultOut,
    OptimizeSuggestion,
    RewriteRequest,
    RewriteResultOut,
)
from app.services import resume_repository as repo
from app.utils.llm_client import llm_client

logger = get_logger("api.optimize")
router = APIRouter()


@router.post("/suggestions", response_model=OptimizeResultOut, summary="生成优化建议")
async def get_suggestions(
    payload: OptimizeRequest, db: Session = Depends(get_db)
) -> OptimizeResultOut:
    """针对目标岗位（可选）生成简历优化建议。"""
    raw_text = _load_resume_text(db, payload.resume_id)

    raw = generate_optimize_suggestions(raw_text, payload.target_jd)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    suggestions: list[OptimizeSuggestion] = []
    for item in data.get("suggestions") or []:
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

    return OptimizeResultOut(resume_id=payload.resume_id, suggestions=suggestions)


@router.post("/rewrite", response_model=RewriteResultOut, summary="段落重写")
async def rewrite_paragraph(payload: RewriteRequest) -> RewriteResultOut:
    """对一段文本做润色重写，可选附目标岗位让风格更贴合。"""
    text = (payload.paragraph or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="paragraph 不能为空")

    if not llm_client.available:
        # LLM 未配置时退化为去除多余空白的占位重写
        return RewriteResultOut(
            original=text,
            rewritten=" ".join(text.split()),
            highlights=["(LLM 未配置，仅返回去除多余空白的版本)"],
        )

    role_hint = (
        f"目标岗位：{payload.target_role}\n请使风格贴合该岗位的招聘偏好。"
        if payload.target_role
        else "通用技术简历风格。"
    )
    system_msg = (
        "你是一位资深中文简历优化顾问。你的输出必须是合法 JSON，"
        "不能有任何文字说明、Markdown、代码块。"
    )
    prompt = (
        f"{role_hint}\n\n请对下面这段简历文本做精炼重写，强调动作动词与量化成果，"
        "保持事实，不要添加未提及的成就。\n\n"
        "JSON 结构：\n"
        "{\n"
        '  "rewritten": "重写后的整段文本",\n'
        '  "highlights": ["改写要点1", "改写要点2", ...]   // 2-4 条\n'
        "}\n\n"
        f"【原文】\n{text[:4000]}\n\n只输出 JSON 对象本身。"
    )

    parsed = llm_client.invoke_json(prompt=prompt, system=system_msg, default=None) or {}
    rewritten = str(parsed.get("rewritten") or "").strip() or text
    highlights = [str(h) for h in (parsed.get("highlights") or []) if str(h).strip()]
    logger.info("rewrite finished", original_len=len(text), rewritten_len=len(rewritten))
    return RewriteResultOut(original=text, rewritten=rewritten, highlights=highlights[:4])


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
