"""Parser Agent 节点 - 基于 LLM 从 raw_text 中提取结构化简历信息。

设计原则：
1. 仅依赖 ``app.utils.llm_client.llm_client``（封装的统一 LLM 客户端）
2. 强制输出 JSON 格式 —— 让 qwen3-vl-plus 等模型走 ``response_format=json_object``
3. 失败时返回合理占位，不影响上层链路
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.utils.helpers import truncate
from app.utils.llm_client import llm_client

logger = get_logger("agent.parser")

# 系统提示词：明确角色、输出格式约束
_SYSTEM_PROMPT = (
    "你是一个专业的中文简历解析助手。"
    "你的任务是：从用户提供的简历原文中，"
    "提取关键信息，并严格按照下面的 JSON Schema 输出 JSON。"
    "要求："
    "1. 仅输出 JSON，不要输出任何解释、引号外文字或 Markdown 代码块；"
    "2. 字段必须完整；无法从文中确定的字段填 null 或空数组；"
    "3. 中文姓名优先，邮件/电话保持原文；"
    "4. skills 字段返回数组，元素为技能名，大小写统一为小写或原样；"
    "5. work_history 按时间倒序，period 字段保留原文的起止时间（例如 '2022.03 - 至今'）。"
)

# 给 LLM 参考的 JSON 结构说明（写在 Human Prompt 中，便于 Qwen 理解）
_SCHEMA_HINT = """
期望的 JSON 输出结构（严格遵守字段名与类型）：
{
  "name": "string | null",
  "email": "string | null",
  "phone": "string | null",
  "gender": "string | null",
  "age": "number | null",
  "education_level": "string | null",
  "years_of_experience": "number | null",
  "skills": ["string"],
  "summary": "string | null",
  "work_history": [
    {
      "company": "string",
      "role": "string",
      "period": "string",
      "highlights": ["string"]
    }
  ],
  "projects": [
    {
      "name": "string",
      "description": "string",
      "role": "string | null",
      "technologies": ["string"]
    }
  ]
}

请直接输出 JSON。
"""


def _fallback(raw_text: str) -> dict:
    """无 LLM / 失败时的简单启发式解析 —— 至少把原文 & 启发式技能抽出。"""
    text = raw_text or ""
    return {
        "name": None,
        "email": None,
        "phone": None,
        "education_level": None,
        "years_of_experience": None,
        "skills": _heuristic_skills(text),
        "summary": truncate(text, 500),
        "work_history": [],
        "projects": [],
        "_note": "heuristic_fallback: LLM unavailable or failed",
    }


_COMMON_SKILL_KEYWORDS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "fastapi",
    "django",
    "flask",
    "spring",
    "node",
    "react",
    "vue",
    "postgresql",
    "mysql",
    "redis",
    "mongodb",
    "docker",
    "kubernetes",
    "k8s",
    "git",
    "linux",
    "aws",
    "阿里云",
    "c++",
    "c#",
    "go",
    "rust",
    "scala",
    "pandas",
    "pytorch",
    "tensorflow",
    "sql",
    "nosql",
    "spark",
    "hadoop",
    "kafka",
    "rabbitmq",
    "openapi",
    "rest",
    "grpc",
)


def _heuristic_skills(text: str) -> list[str]:
    low = text.lower()
    return [kw for kw in _COMMON_SKILL_KEYWORDS if kw in low]


def run(raw_text: str) -> dict:
    """执行简历结构化解析。

    返回的 dict 包含：
    - parsed_resume: 结构化字段对象
    - parse_confidence: 0.0 ~ 1.0 的置信度（有 LLM 时给 0.85，启发式时 0.3）
    - raw_text_len: 原文长度
    - provider: 实际使用的 LLM provider（或 'stub'）
    """
    logger.info("parser agent running", text_len=len(raw_text or ""))

    if not raw_text or not raw_text.strip():
        return {
            "parsed_resume": _fallback(""),
            "parse_confidence": 0.0,
            "raw_text_len": 0,
            "provider": "empty",
        }

    # LLM 未配置或依赖缺失时，走启发式 fallback
    if not llm_client.available:
        logger.warning("LLM unavailable — fall back to heuristic parser")
        return {
            "parsed_resume": _fallback(raw_text),
            "parse_confidence": 0.3,
            "raw_text_len": len(raw_text),
            "provider": "heuristic",
        }

    prompt = (
        "以下是一份简历的 OCR / 纯文本内容（可能有排版噪声）：\n"
        "----------------------------------------\n"
        f"{truncate(raw_text, 8000)}\n"
        "----------------------------------------\n"
        f"{_SCHEMA_HINT}"
    )

    data = llm_client.invoke_json(
        prompt=prompt,
        system=_SYSTEM_PROMPT,
        default=None,
    )

    if not data or not isinstance(data, (dict, list)):
        logger.warning("parser agent got empty/invalid JSON — fallback")
        return {
            "parsed_resume": _fallback(raw_text),
            "parse_confidence": 0.3,
            "raw_text_len": len(raw_text),
            "provider": f"{llm_client.provider}(fallback)",
        }

    # 兼容 list：某些模型可能 [{...}]
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        data = data[0]

    return {
        "parsed_resume": _normalize(data),
        "parse_confidence": 0.85,
        "raw_text_len": len(raw_text),
        "provider": llm_client.provider,
    }


def _normalize(data: dict) -> dict:
    """确保输出字段都存在，防止上层 KeyError。"""
    return {
        "name": data.get("name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "gender": data.get("gender"),
        "age": data.get("age"),
        "education_level": data.get("education_level"),
        "years_of_experience": data.get("years_of_experience"),
        "skills": _as_list(data.get("skills")),
        "summary": data.get("summary"),
        "work_history": _as_work_history(data.get("work_history")),
        "projects": _as_projects(data.get("projects")),
    }


def _as_list(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        # 兼容 "Python, FastAPI" 这种逗号分隔
        return [s.strip() for s in v.replace("，", ",").split(",") if s.strip()]
    return []


def _as_work_history(v) -> list[dict]:
    if not isinstance(v, list):
        return []
    out: list[dict] = []
    for item in v:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "company": item.get("company"),
                "role": item.get("role"),
                "period": item.get("period"),
                "highlights": _as_list(item.get("highlights")),
            }
        )
    return out


def _as_projects(v) -> list[dict]:
    if not isinstance(v, list):
        return []
    out: list[dict] = []
    for item in v:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": item.get("name"),
                "description": item.get("description"),
                "role": item.get("role"),
                "technologies": _as_list(item.get("technologies")),
            }
        )
    return out
