"""简历优化 Tool：基于简历 + 可选 JD 生成优化建议。"""
from __future__ import annotations

import json

from app.core.logging import get_logger
from app.utils.llm_client import llm_client

logger = get_logger("agent.tools.optimize")


def generate_optimize_suggestions(resume_text: str, jd_text: str | None = None) -> str:
    """针对一份简历（可选附带目标岗位 JD）生成逐条优化建议，返回 JSON 字符串。

    Args:
        resume_text: 简历的全文内容。
        jd_text: 可选 —— 目标岗位描述（Job Description），若提供则建议会更有针对性。

    Returns:
        JSON 字符串，包含 suggestions 数组，每一项:
        {"category": "技能/工作经历/项目经历/整体结构",
         "original": "原文片段（若有）",
         "improved": "改进后的写法",
         "reason": "为什么这样改更好（中文）"}
    """
    if not resume_text or not resume_text.strip():
        return json.dumps({"error": "resume_text is empty"}, ensure_ascii=False, indent=2)

    jd_hint = f"\n【目标岗位 JD】\n{jd_text[:4000]}" if jd_text else "\n（未提供目标岗位，按通用技术简历标准优化）"

    prompt = (
        "你是一位资深中文简历优化顾问。请针对下面这份简历提出 3-6 条具体可执行的优化建议，"
        "严格按 JSON 输出，不要输出 Markdown 代码块。\n\n"
        "JSON 结构：\n"
        '{"suggestions": ['
        '{"category": "技能/工作经历/项目经历/整体结构/其他", '
        '"original": "原文中的问题片段（若无法定位则留空字符串）", '
        '"improved": "改进后的写法建议", '
        '"reason": "为什么这样改更好（中文）"}'
        "]}\n\n"
        f"【简历】\n{resume_text[:8000]}{jd_hint}\n\n"
        "只输出 JSON，不要输出任何解释文字。"
    )

    if not llm_client.available:
        return json.dumps(
            {
                "suggestions": [
                    {
                        "category": "整体结构",
                        "original": "",
                        "improved": "在简历顶部添加 2-3 行个人亮点/目标岗位总结，把匹配 JD 的关键词放在前面。",
                        "reason": "(LLM 未配置，启发式建议) 招聘方浏览时间有限，顶部亮点能更快抓住注意力。",
                    },
                    {
                        "category": "工作经历",
                        "original": "",
                        "improved": "每段工作经历使用「动作动词 + 具体量化成果」的格式，例如 '主导 x 项目，将 y 指标提升 z%'。",
                        "reason": "(LLM 未配置，启发式建议) 量化结果比定性描述更有说服力。",
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        )

    data = llm_client.invoke_json(prompt=prompt, system="你是一位资深中文简历优化顾问。", default=None)
    if not data:
        return json.dumps(
            {"error": "LLM returned empty or invalid JSON", "suggestions": []},
            ensure_ascii=False,
            indent=2,
        )
    logger.info("generate_optimize_suggestions tool finished", count=len(data.get("suggestions", [])))
    return json.dumps(data, ensure_ascii=False, indent=2)
