"""Optimizer Agent 节点 - 生成优化建议。

薄包装：复用 ``app.agents.tools.optimize_tools.generate_optimize_suggestions``。
"""
from __future__ import annotations

import json

from app.agents.tools.optimize_tools import generate_optimize_suggestions
from app.core.logging import get_logger

logger = get_logger("agent.optimizer")


def run(resume_text: str, target_jd: str | None = None) -> dict:
    """对简历生成 3-6 条结构化优化建议。

    Args:
        resume_text: 简历原文
        target_jd: 可选目标岗位 JD，若提供则建议会更有针对性
    Returns:
        dict 含 optimize_suggestions: list[{category, original, improved, reason}]
    """
    raw = generate_optimize_suggestions(resume_text or "", target_jd)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = {}

    if not isinstance(data, dict) or "error" in data:
        logger.warning("optimizer tool returned error or non-dict", payload=str(raw)[:200])
        return {"optimize_suggestions": []}

    suggestions = data.get("suggestions") or []
    if not isinstance(suggestions, list):
        suggestions = []

    logger.info("optimizer agent finished", count=len(suggestions))
    return {"optimize_suggestions": suggestions}
