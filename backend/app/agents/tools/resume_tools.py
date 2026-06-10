"""简历相关 Tools：解析、摘要。"""
from __future__ import annotations

import json

from app.agents.nodes.parser_agent import run as run_parser
from app.core.logging import get_logger
from app.utils.llm_client import llm_client

logger = get_logger("agent.tools.resume")


def parse_resume_text(resume_text: str) -> str:
    """从简历的纯文本中提取结构化信息并返回 JSON 字符串。

    Args:
        resume_text: 简历的全文内容（从 PDF/Word/图片中提取的文本）。

    Returns:
        一段 JSON 字符串，字段包含：name、email、phone、education_level、
        years_of_experience、skills（数组）、work_history（数组）、projects（数组）、
        summary 等。
    """
    if not resume_text or not resume_text.strip():
        return json.dumps({"error": "resume_text is empty"}, ensure_ascii=False, indent=2)

    result = run_parser(resume_text) or {}
    parsed = result.get("parsed_resume") or {}
    confidence = result.get("parse_confidence") or 0.0
    provider = result.get("provider") or "unknown"

    out = {
        "parse_confidence": confidence,
        "provider": provider,
        "summary": parsed.get("summary"),
        "name": parsed.get("name"),
        "email": parsed.get("email"),
        "phone": parsed.get("phone"),
        "education_level": parsed.get("education_level"),
        "years_of_experience": parsed.get("years_of_experience"),
        "skills": parsed.get("skills") or [],
        "work_history": parsed.get("work_history") or [],
        "projects": parsed.get("projects") or [],
    }
    logger.info("parse_resume_text tool finished", confidence=confidence, provider=provider)
    return json.dumps(out, ensure_ascii=False, indent=2)


def summarize_resume(parsed_resume_json: str) -> str:
    """把 parse_resume_text 输出的 JSON 简历结构，整理成一段中文摘要。

    Args:
        parsed_resume_json: parse_resume_text 返回的 JSON 字符串。

    Returns:
        一段 3-5 句话的中文摘要，突出候选人的核心技能、经验年限与亮点项目。
    """
    try:
        parsed = json.loads(parsed_resume_json) if isinstance(parsed_resume_json, str) else parsed_resume_json
    except Exception as exc:  # noqa: BLE001
        return f"输入不是合法 JSON: {exc}"

    if not isinstance(parsed, dict) or not parsed.get("skills"):
        return "输入的简历结构不完整，无法生成摘要。"

    # 直接让 LLM 做摘要；若不可用则启发式拼接
    skills = ", ".join([str(s) for s in (parsed.get("skills") or [])])
    name = parsed.get("name") or "候选人"
    years = parsed.get("years_of_experience")
    edu = parsed.get("education_level") or "学历未知"
    highlights = ""
    wh = parsed.get("work_history") or []
    if wh:
        top = wh[:2]
        highlights = "；".join(
            f"{item.get('company')}@{item.get('role')}" for item in top if item
        )

    prompt = (
        f"请根据以下结构化简历信息，用 3-5 句中文总结候选人的亮点：\n"
        f"- 姓名：{name}\n"
        f"- 工作年限：{years}\n"
        f"- 学历：{edu}\n"
        f"- 主要技能：{skills}\n"
        f"- 最近工作：{highlights}\n"
        f"要求：语气客观、突出候选人与岗位相关的亮点，不要超过 200 字。"
    )

    if not llm_client.available:
        return (
            f"{name}，约 {years} 年工作经验，学历 {edu}，"
            f"核心技能：{skills}。最近工作：{highlights or '无'}。"
        )

    return llm_client.invoke(prompt, system="你是一位资深技术招聘顾问。")
