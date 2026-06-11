"""Agent Tools —— 把业务功能封装成 LangChain Tools，供大模型自动调用。

对外暴露两套接口：
1. ``get_all_tools()`` -> list[Tool]，供 LangChain bind_tools 原生路径使用
2. ``invoke_tool(name, **kwargs)`` -> str，直接执行工具函数（绕过 schema 校验的强容错调用）
"""
from __future__ import annotations

import json
from typing import Any

from app.agents.tools.match_tools import match_resume_to_jd
from app.agents.tools.optimize_tools import generate_optimize_suggestions
from app.agents.tools.resume_tools import parse_resume_text, summarize_resume
from app.core.logging import get_logger

logger = get_logger("agent.tools.registry")

__all__ = [
    "get_all_tools",
    "invoke_tool",
    "parse_resume_text",
    "summarize_resume",
    "match_resume_to_jd",
    "generate_optimize_suggestions",
]


# ---------- 参数名的常见变体映射（模型经常瞎写字段名，需要兜底） ----------
_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "parse_resume_text": {
        "resume_text": ("resume_text", "raw_text", "text", "content", "简历文本", "resume", "input"),
    },
    "summarize_resume": {
        "parsed_resume_json": ("parsed_resume_json", "parsed_resume", "resume_json", "json_data", "json", "data"),
    },
    "match_resume_to_jd": {
        "resume_text": ("resume_text", "resume", "text", "简历", "candidate", "input"),
        "jd_text": ("jd_text", "jd", "job_description", "job", "岗位描述", "职位描述", "description"),
    },
    "generate_optimize_suggestions": {
        "resume_text": ("resume_text", "resume", "text", "简历", "input"),
        "jd_text": ("jd_text", "jd", "job_description", "job", "岗位描述", "description"),
    },
}


def _coerce_args(tool_name: str, incoming: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 返回的任意字段名对齐到函数签名所需的字段名。"""
    if incoming is None:
        return {}
    if not isinstance(incoming, dict):
        # 有些模型会把整个 args 当成字符串
        try:
            incoming = json.loads(str(incoming))
        except (TypeError, ValueError):
            incoming = {"resume_text": str(incoming)}

    alias_map = _ALIASES.get(tool_name, {})
    out: dict[str, Any] = {}
    for canonical_name, variants in alias_map.items():
        for v in variants:
            if v in incoming and incoming[v] not in (None, "", [], {}):
                out[canonical_name] = incoming[v]
                break

    # 还有没 aliased 的字段，直接同名透传
    for k, v in incoming.items():
        if k not in alias_map and v not in (None, "", [], {}):
            out.setdefault(k, v)

    return out


def invoke_tool(name: str, **kwargs: Any) -> str:
    """根据工具名直接调用底层 Python 函数。

    相比 ``StructuredTool.invoke()``：
    - 不依赖 Pydantic schema 校验，避免字段名漂移导致的 validation_error
    - 自动把常见的字段名变体（raw_text/resume_text、jd/job_description 等）归一化
    - 缺必填参数时返回带说明的 JSON 字符串而不是抛异常

    返回值：工具函数返回的 JSON 字符串（和各 tool 的 return 一致）。
    """
    tools: dict[str, Any] = {
        "parse_resume_text": parse_resume_text,
        "summarize_resume": summarize_resume,
        "match_resume_to_jd": match_resume_to_jd,
        "generate_optimize_suggestions": generate_optimize_suggestions,
    }
    func = tools.get(name)
    if func is None:
        return json.dumps(
            {"error": f"unknown tool: {name}", "available_tools": list(tools.keys())},
            ensure_ascii=False,
        )

    normalized = _coerce_args(name, kwargs)

    # 工具都只有一个必填参数（resume_text 或 parsed_resume_json）
    required_keys = {
        "parse_resume_text": ("resume_text",),
        "summarize_resume": ("parsed_resume_json",),
        "match_resume_to_jd": ("resume_text", "jd_text"),
        "generate_optimize_suggestions": ("resume_text",),
    }

    missing = [k for k in required_keys.get(name, ()) if k not in normalized]
    if missing:
        return json.dumps(
            {
                "error": f"missing required arguments: {missing}",
                "received_keys": list(normalized.keys()),
                "hint": f"expected keys: {list(required_keys.get(name, ()))}",
            },
            ensure_ascii=False,
        )

    logger.info("tool invoked", tool=name, received_keys=list(normalized.keys()))
    try:
        return func(**normalized)
    except Exception as exc:  # noqa: BLE001
        logger.error("tool function raised", tool=name, error=str(exc))
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)


def get_all_tools():
    """返回全部可用 Tool 的列表（供 Agent bind_tools 使用）。

    用显式 Pydantic v2 BaseModel 定义 args_schema，避免 ``StructuredTool.from_function()``
    在不同 LangChain / Pydantic 版本之间漂移。
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # ---------- 每个工具一个显式 schema ----------
    class ParseResumeTextSchema(BaseModel):
        resume_text: str = Field(..., description="简历的全文内容（从 PDF/Word/图片中提取的文本）")

    class SummarizeResumeSchema(BaseModel):
        parsed_resume_json: str = Field(..., description="parse_resume_text 工具返回的 JSON 字符串")

    class MatchResumeToJdSchema(BaseModel):
        resume_text: str = Field(..., description="候选人的简历全文内容")
        jd_text: str = Field(..., description="目标岗位的职位描述全文内容")

    class GenerateOptimizeSuggestionsSchema(BaseModel):
        resume_text: str = Field(..., description="候选人的简历全文内容")
        jd_text: str | None = Field(default=None, description="可选：目标岗位的职位描述，有则建议更有针对性")

    # ---------- 构造 Tool 实例 ----------
    return [
        StructuredTool.from_function(
            func=parse_resume_text,
            name="parse_resume_text",
            description=(
                "从简历的纯文本内容中提取结构化信息，"
                "包括：姓名、邮箱、电话、学历、工作年限、技能列表、工作经历、项目经历。"
                "当用户上传了一份简历、或提供了简历文本、且需要了解简历的具体内容（候选人背景）时调用。"
            ),
            args_schema=ParseResumeTextSchema,
        ),
        StructuredTool.from_function(
            func=summarize_resume,
            name="summarize_resume",
            description=(
                "把已解析的简历结构（parse_resume_text 的结果 JSON 字符串）整理成一段中文摘要，"
                "突出候选人的核心技能、行业经验年限与亮点项目。"
            ),
            args_schema=SummarizeResumeSchema,
        ),
        StructuredTool.from_function(
            func=match_resume_to_jd,
            name="match_resume_to_jd",
            description=(
                "将一份简历文本与一段岗位描述（JD）进行匹配分析，"
                "输出匹配度评分、候选人优势、能力缺口。当用户提出「这份简历是否适合某个岗位」"
                "「分析匹配度」「帮我对比」这类问题时调用。需要同时提供 resume_text 和 jd_text。"
            ),
            args_schema=MatchResumeToJdSchema,
        ),
        StructuredTool.from_function(
            func=generate_optimize_suggestions,
            name="generate_optimize_suggestions",
            description=(
                "针对一份简历（可选附带目标岗位 JD）生成优化建议，"
                "逐条指出问题段落、改进后的写法、以及修改原因。"
                "当用户问「如何优化」「给简历提建议」「怎么改更好」时调用。"
            ),
            args_schema=GenerateOptimizeSuggestionsSchema,
        ),
    ]
