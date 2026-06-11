"""Matcher Agent 节点 - 基于 JD 计算匹配度。

薄包装：复用 ``app.agents.tools.match_tools.match_resume_to_jd``（已含 LLM + heuristic
fallback 逻辑），节点只负责协议转换（JSON str -> dict）和 state 字段映射。
"""
from __future__ import annotations

import json

from app.agents.tools.match_tools import match_resume_to_jd
from app.core.logging import get_logger

logger = get_logger("agent.matcher")


def run(resume_text: str, jd: str) -> dict:
    """对一份简历的全文与 JD 做匹配。

    Args:
        resume_text: 简历原文
        jd: 目标岗位 JD 文本
    Returns:
        dict 包含 match_score / match_breakdown / match_reasons / match_strengths
        / match_gaps / match_reasoning
    """
    raw = match_resume_to_jd(resume_text or "", jd or "")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = {}

    if not isinstance(data, dict) or "error" in data:
        logger.warning("matcher tool returned error or non-dict", payload=str(raw)[:200])
        return {
            "match_score": 0.0,
            "match_breakdown": {"skill_match": 0.0, "experience_match": 0.0, "education_match": 0.0},
            "match_reasons": [],
            "match_strengths": [],
            "match_gaps": [],
            "match_reasoning": str(data.get("error", "")) if isinstance(data, dict) else "",
        }

    try:
        score = float(data.get("overall_score") or 0)
    except (TypeError, ValueError):
        score = 0.0

    strengths = [str(s) for s in (data.get("strengths") or [])]
    gaps = [str(g) for g in (data.get("gaps") or [])]
    reasoning = str(data.get("reasoning") or "")

    logger.info("matcher agent finished", score=score, strengths=len(strengths), gaps=len(gaps))
    return {
        "match_score": score,
        # tool 暂不返回拆解维度，留 0.0 占位（schema 仍兼容）
        "match_breakdown": {"skill_match": 0.0, "experience_match": 0.0, "education_match": 0.0},
        "match_reasons": strengths + gaps,
        "match_strengths": strengths,
        "match_gaps": gaps,
        "match_reasoning": reasoning,
    }
