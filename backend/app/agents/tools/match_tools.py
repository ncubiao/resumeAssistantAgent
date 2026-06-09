"""岗位匹配 Tool：对比简历与 JD。"""
from __future__ import annotations

import json

from app.core.logging import get_logger
from app.utils.llm_client import llm_client

logger = get_logger("agent.tools.match")


def match_resume_to_jd(resume_text: str, jd_text: str) -> str:
    """分析一份简历与目标岗位（JD）的匹配情况，返回 JSON 字符串。

    Args:
        resume_text: 简历的全文内容。
        jd_text: 目标岗位描述（Job Description）的全文。

    Returns:
        JSON 字符串，包含:
        - overall_score: 0-100 的匹配度评分
        - strengths: 候选人契合岗位的优势（字符串数组）
        - gaps: 候选人相对岗位的能力缺口（字符串数组）
        - reasoning: 简要判断过程（中文）
    """
    if not resume_text or not resume_text.strip():
        return json.dumps({"error": "resume_text is empty"}, ensure_ascii=False, indent=2)
    if not jd_text or not jd_text.strip():
        return json.dumps({"error": "jd_text is empty"}, ensure_ascii=False, indent=2)

    # 走 LLM 分析；不可用时走启发式关键词匹配
    prompt = (
        "你是一位资深招聘经理。请分析下方简历与目标岗位的匹配情况，严格按 JSON 输出，不要输出 Markdown 代码块。\n"
        "JSON 结构：\n"
        '{"overall_score": 数字0-100, "strengths": [字符串数组], '
        '"gaps": [字符串数组], "reasoning": "一句话说明判断依据"}\n\n'
        f"【简历】\n{resume_text[:6000]}\n\n"
        f"【目标岗位 JD】\n{jd_text[:6000]}\n\n"
        "只输出 JSON，不要输出任何解释文字。"
    )

    if not llm_client.available:
        # 启发式：简单关键词重合
        import re

        tokens_resume = set(re.findall(r"[\w\u4e00-\u9fa5]+", resume_text.lower()))
        tokens_jd = set(re.findall(r"[\w\u4e00-\u9fa5]+", jd_text.lower()))
        common = tokens_resume & tokens_jd
        score = min(100, int(len(common) / max(1, len(tokens_jd)) * 150))
        return json.dumps(
            {
                "overall_score": score,
                "strengths": [f"简历与 JD 共享 {len(common)} 个关键词"] if common else [],
                "gaps": ["无法通过 LLM 做深度分析（LLM 未配置），以上分数仅供参考"],
                "reasoning": "(LLM 未配置，启发式匹配)",
            },
            ensure_ascii=False,
            indent=2,
        )

    data = llm_client.invoke_json(prompt=prompt, system="你是一位资深招聘经理。", default=None)
    if not data:
        return json.dumps(
            {"error": "LLM returned empty or invalid JSON", "overall_score": 0, "strengths": [], "gaps": [], "reasoning": ""},
            ensure_ascii=False,
            indent=2,
        )
    logger.info("match_resume_to_jd tool finished", score=data.get("overall_score"))
    return json.dumps(data, ensure_ascii=False, indent=2)
