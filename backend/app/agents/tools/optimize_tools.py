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

    system_msg = (
        "你是一位资深中文简历优化顾问。你的所有输出必须是合法 JSON，"
        " 不能有任何文字说明、Markdown、代码块。"
    )
    prompt = (
        "请针对下面这份简历提出 3-6 条具体可执行的优化建议。\n\n"
        "JSON 结构要求（字段名、字段类型必须一致）：\n"
        "{\n"
        '  "suggestions": [\n'
        '    {"category": "技能/工作经历/项目经历/整体结构/其他",\n'
        '     "original": "原文中的问题片段（若无法定位则留空字符串）",\n'
        '     "improved": "改进后的写法建议",\n'
        '     "reason": "为什么这样改更好（中文）"}\n'
        "  ]\n"
        "}\n\n"
        "注意：\n"
        "- 不允许输出 ```json 或 ``` 或任何 Markdown 标记；\n"
        "- 不允许输出 JSON 之外的任何文字；\n"
        "- suggestions 数组至少 3 条，不超过 6 条。\n\n"
        f"【简历】\n{resume_text[:8000]}{jd_hint}\n\n"
        "只输出 JSON 对象本身。"
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

    # 两步容错：强约束 + 智能提取 JSON
    parsed = llm_client.invoke_json(prompt=prompt, system=system_msg, default=None)
    if parsed is None:
        raw_reply = llm_client.invoke(prompt=prompt, system=system_msg) or ""
        from app.utils.llm_client import _extract_json

        parsed = _extract_json(raw_reply)

    suggestions = []
    if isinstance(parsed, dict):
        s = parsed.get("suggestions") or parsed.get("items") or parsed.get("result") or []
        if isinstance(s, list):
            for item in s:
                if isinstance(item, dict):
                    suggestions.append({
                        "category": str(item.get("category") or "其他"),
                        "original": str(item.get("original") or ""),
                        "improved": str(item.get("improved") or ""),
                        "reason": str(item.get("reason") or ""),
                    })

    if not suggestions:
        suggestions = [
            {
                "category": "整体结构",
                "original": "",
                "improved": "在简历顶部添加个人亮点摘要，并把与目标岗位相关的关键词前置。",
                "reason": "让招聘方在 3 秒内捕捉到你的核心匹配度。",
            }
        ]

    logger.info("generate_optimize_suggestions tool finished", count=len(suggestions))
    return json.dumps({"suggestions": suggestions[:6]}, ensure_ascii=False, indent=2)
