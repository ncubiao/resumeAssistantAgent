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

    # 用更强约束的 JSON 指令
    system_msg = (
        "你是一位资深招聘经理，擅长对照岗位描述分析候选人的匹配程度。"
        " 你的所有输出必须是合法 JSON，不能有任何文字说明、Markdown、代码块。"
    )
    prompt = (
        "请分析以下简历与目标岗位的匹配情况，仅输出 JSON，字段名与类型必须完全符合：\n\n"
        "JSON 结构要求（字段名、字段类型必须一致）：\n"
        "{\n"
        '  "overall_score": number,     // 0-100 整数，整体匹配度\n'
        '  "strengths": [string, ...],  // 2-4 条字符串，候选人与岗位匹配的亮点\n'
        '  "gaps":      [string, ...],  // 2-4 条字符串，候选人相对岗位的能力缺口\n'
        '  "reasoning": string          // 一句话中文，解释评分依据\n'
        "}\n\n"
        "注意：\n"
        "- 不允许输出 ```json 或 ``` 或任何 Markdown 标记；\n"
        "- 不允许输出 JSON 之外的任何文字（如好的/以下是/等）；\n"
        "- overall_score 必须是 0-100 的整数，不要加引号。\n\n"
        f"【简历】\n{resume_text[:6000]}\n\n"
        f"【目标岗位 JD】\n{jd_text[:6000]}\n\n"
        "只输出 JSON 对象本身。"
    )

    if not llm_client.available:
        import re as _re

        tokens_resume = set(_re.findall(r"[\w\u4e00-\u9fa5]+", resume_text.lower()))
        tokens_jd = set(_re.findall(r"[\w\u4e00-\u9fa5]+", jd_text.lower()))
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

    # 两步容错：先让 LLM 生成（允许文字+JSON），再用智能提取解析
    raw_reply = llm_client.invoke(prompt=prompt, system=system_msg) or ""
    parsed = None

    # 1）先用 invoke_json 的内部解析（经过 response_format 约束的纯 JSON 路径）
    parsed = llm_client.invoke_json(prompt=prompt, system=system_msg, default=None)

    # 2）若 1）失败，用更强的文本 JSON 提取
    if parsed is None:
        from app.utils.llm_client import _extract_json

        parsed = _extract_json(raw_reply)

    # 3）校验字段，缺失则补默认值
    if not isinstance(parsed, dict):
        parsed = {}
    overall_score = parsed.get("overall_score") or parsed.get("overallScore") or 0
    try:
        overall_score = int(float(overall_score))
    except (ValueError, TypeError):
        overall_score = 0

    strengths = parsed.get("strengths") or parsed.get("strength") or []
    if not isinstance(strengths, list):
        strengths = [str(strengths)]

    gaps = parsed.get("gaps") or parsed.get("gap") or []
    if not isinstance(gaps, list):
        gaps = [str(gaps)]

    reasoning = str(parsed.get("reasoning") or parsed.get("reason") or "")

    result = {
        "overall_score": overall_score,
        "strengths": [str(s) for s in strengths][:6],
        "gaps": [str(g) for g in gaps][:6],
        "reasoning": reasoning[:500],
    }
    logger.info("match_resume_to_jd tool finished", score=result["overall_score"])
    return json.dumps(result, ensure_ascii=False, indent=2)
