"""Analyzer Agent 节点 - 对结构化简历进行启发式打分分析。

设计选择：纯派生、不调 LLM。理由：
1. 学历/年限/亮点这些信息从 parsed_resume 派生即可，不值得一次 LLM 调用；
2. 让 graph 在 LLM 不可用时也能跑通分析层；
3. 与 matcher/optimizer（调 LLM）形成层次：分析层启发式，决策层智能。
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("agent.analyzer")


# 学历 -> 分数映射（中文 + 英文常见写法）
_EDU_SCORE: dict[str, int] = {
    "博士": 90, "phd": 90, "doctor": 90, "doctorate": 90,
    "硕士": 75, "master": 75, "msc": 75, "ma": 75,
    "本科": 60, "学士": 60, "bachelor": 60, "bsc": 60, "ba": 60, "undergraduate": 60,
    "大专": 40, "专科": 40, "associate": 40, "diploma": 40,
    "高中": 25, "high school": 25,
}


def _education_score(level: str | None) -> int:
    if not level:
        return 30
    low = str(level).lower().strip()
    for kw, score in _EDU_SCORE.items():
        if kw in low:
            return score
    return 30


def _experience_score(years: float | int | None) -> int:
    """经验年限 -> 0-100 分。每年 12 分，封顶 100。"""
    if years is None:
        return 0
    try:
        y = float(years)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, int(y * 12)))


def _collect_highlights(parsed: dict, limit: int = 5) -> list[str]:
    """从 work_history 与 projects 抽取 highlights / description，去重并取前 N 条。"""
    out: list[str] = []
    for w in parsed.get("work_history") or []:
        if not isinstance(w, dict):
            continue
        for h in w.get("highlights") or []:
            text = str(h).strip()
            if text and text not in out:
                out.append(text)
            if len(out) >= limit:
                return out
    for p in parsed.get("projects") or []:
        if not isinstance(p, dict):
            continue
        desc = str(p.get("description") or "").strip()
        if desc and desc not in out:
            out.append(desc)
        if len(out) >= limit:
            return out
    return out


def _collect_weaknesses(parsed: dict) -> list[str]:
    """缺失字段检查，每条生成一句中文提示。"""
    weaknesses: list[str] = []
    if not parsed.get("skills"):
        weaknesses.append("简历未明确列出技能关键词，建议在显著位置补充技术栈清单。")
    if not parsed.get("work_history"):
        weaknesses.append("缺少工作经历描述，无法体现实际产出。")
    years = parsed.get("years_of_experience") or 0
    try:
        if float(years) < 1:
            weaknesses.append("工作经验不足 1 年，建议突出项目经验和实习成果。")
    except (TypeError, ValueError):
        pass
    if not parsed.get("email") and not parsed.get("phone"):
        weaknesses.append("缺少联系方式（邮箱/电话），招聘方无法触达。")
    if not parsed.get("projects"):
        weaknesses.append("缺少项目经历，建议补充 2-3 个具有量化成果的项目。")
    return weaknesses


def run(parsed_resume: dict | None) -> dict:
    """对结构化简历做启发式打分与亮点/弱项分析。

    Args:
        parsed_resume: parser_agent 输出的结构化简历字典。
    Returns:
        dict 包含 skills / highlights / weaknesses / education_score / experience_score
    """
    parsed = parsed_resume or {}
    skills = list(parsed.get("skills") or [])
    education_score = _education_score(parsed.get("education_level"))
    experience_score = _experience_score(parsed.get("years_of_experience"))
    highlights = _collect_highlights(parsed)
    weaknesses = _collect_weaknesses(parsed)

    logger.info(
        "analyzer agent finished",
        skills_count=len(skills),
        edu_score=education_score,
        exp_score=experience_score,
        highlights=len(highlights),
        weaknesses=len(weaknesses),
    )
    return {
        "skills": skills,
        "highlights": highlights,
        "weaknesses": weaknesses,
        "education_score": education_score,
        "experience_score": experience_score,
    }
