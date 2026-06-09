"""Agent Tools —— 把业务功能封装成 LangChain Tools，供大模型自动调用。"""

from app.agents.tools.resume_tools import parse_resume_text, summarize_resume
from app.agents.tools.match_tools import match_resume_to_jd
from app.agents.tools.optimize_tools import generate_optimize_suggestions

__all__ = [
    "get_all_tools",
    "parse_resume_text",
    "summarize_resume",
    "match_resume_to_jd",
    "generate_optimize_suggestions",
]


def get_all_tools():
    """返回全部可用 Tool 的列表（供 Agent 绑定使用）。"""
    from langchain_core.tools import StructuredTool

    return [
        StructuredTool.from_function(
            func=parse_resume_text,
            name="parse_resume_text",
            description=(
                "从简历的纯文本内容中提取结构化信息，"
                "包括：姓名、邮箱、电话、学历、工作年限、技能列表、工作经历、项目经历。"
                "当用户上传了一份简历、或提供了简历文本、且需要了解简历的具体内容（候选人背景）时调用。"
            ),
        ),
        StructuredTool.from_function(
            func=summarize_resume,
            name="summarize_resume",
            description=(
                "把已解析的简历结构（parse_resume_text 的结果）整理成一段中文摘要，"
                "突出候选人的核心技能、行业经验年限与亮点项目。"
            ),
        ),
        StructuredTool.from_function(
            func=match_resume_to_jd,
            name="match_resume_to_jd",
            description=(
                "将一份简历文本与一段岗位描述（JD）进行匹配分析，"
                "输出匹配度评分、候选人优势、能力缺口。当用户提出「这份简历是否适合某个岗位」"
                "「分析匹配度」「帮我对比」这类问题时调用。需要同时提供简历文本和 JD 文本。"
            ),
        ),
        StructuredTool.from_function(
            func=generate_optimize_suggestions,
            name="generate_optimize_suggestions",
            description=(
                "针对一份简历（可选附带目标岗位 JD）生成优化建议，"
                "逐条指出问题段落、改进后的写法、以及修改原因。"
                "当用户问「如何优化」「给简历提建议」「怎么改更好」时调用。"
            ),
        ),
    ]
