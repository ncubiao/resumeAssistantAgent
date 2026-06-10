"""多轮对话 + Tool Calling 的 Agent 引擎。

两种调用路径（按优先级，按可用性自动切换）：
1. 原生 tool_calls：ChatOpenAI.bind_tools() + 读取 message.tool_calls
2. 结构化提示回落：让模型在回复中以特殊标记选择工具与参数
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.tools import get_all_tools, invoke_tool
from app.core.logging import get_logger
from app.utils.llm_client import llm_client

logger = get_logger("agent.chat")

_SYSTEM_PROMPT = (
    "你是「简历小助手」，一位专业、客观的中文招聘顾问 AI 助手。\n"
    "你可以帮助用户做以下事情：\n"
    "1. 解析简历：提取候选人的姓名、技能、工作经历、项目经历等结构化信息。\n"
    "2. 分析岗位匹配：判断一份简历与某个目标岗位（JD）的匹配度，指出优势与缺口。\n"
    "3. 简历优化：提出具体、可执行的简历修改建议。\n"
    "4. 回答一般性问题：例如简历格式、面试技巧、职业规划等。\n\n"
    "使用工具的规则：\n"
    "- 当你需要从简历中提取结构化信息、或分析简历内容时，才调用工具。\n"
    "- 不要重复调用同一个工具获取同样的结果（如果上一轮已经拿到结果，直接基于结果回答）。\n"
    "- 所有工具的返回值都是 JSON 字符串，你需要理解其含义并用自然语言回答用户。\n"
    "- 如果用户上传了文件（简历/JD），会在用户消息里以【附件】标签明确标注。\n"
    "- 回答要简洁、直接、专业，中文输出，不要使用 Markdown 代码块。\n"
)

_MAX_TOOL_LOOPS = 3  # 防止无限循环：最多调用 3 次工具


@dataclass
class ChatTurn:
    """一次 tool call 记录，用于前端展示调用过程。"""

    tool_name: str
    tool_input: str
    tool_output: str
    truncated_output: str = ""


@dataclass
class AgentResponse:
    answer: str
    tool_calls: list[ChatTurn] = field(default_factory=list)
    provider: str = "unknown"
    used_tools: bool = False


# ---------- 公开入口 ----------

def run_agent(
    user_message: str,
    context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> AgentResponse:
    """执行一轮 Agent 对话。

    Args:
        user_message: 用户当前这条消息的原文。
        context: 可选的会话上下文，用于传递「用户上传的文件」；
                 支持的 key:
                   - "resume_text":  str  —— 用户上传的简历文本
                   - "jd_text":      str  —— 用户上传的岗位描述文本
                   - "parsed_resume_json": str  —— 若之前解析过，可直接提供
        history: 可选的历史消息，列表元素为 {"role": "user"|"assistant", "content": str}。

    Returns:
        AgentResponse: 包含自然语言答案 + tool call 过程记录。
    """
    context = context or {}
    history = history or []

    # 把附件信息加到 user message 里（作为第一段上下文）
    preamble = _build_preamble(context)
    full_user_message = f"{preamble}\n用户: {user_message}" if preamble else user_message

    tools = get_all_tools()
    tool_map = {t.name: t for t in tools}
    tool_descriptions = _format_tool_descriptions(tools)

    tool_turns: list[ChatTurn] = []

    # 1) 先试原生 tool_calls 路径
    answer = _try_native_tool_calls(
        full_user_message, history, tool_map, tool_descriptions, tool_turns, context
    )
    if answer is not None:
        return AgentResponse(
            answer=answer,
            tool_calls=tool_turns,
            provider=llm_client.provider if llm_client.available else "fallback",
            used_tools=len(tool_turns) > 0,
        )

    # 2) 回落：结构化提示 + 模型以标记选择工具
    answer = _run_prompt_based_tool_loop(
        full_user_message, history, tool_map, tool_descriptions, tool_turns, context
    )

    return AgentResponse(
        answer=answer,
        tool_calls=tool_turns,
        provider=llm_client.provider if llm_client.available else "fallback",
        used_tools=len(tool_turns) > 0,
    )


# ---------- 路径 1：原生 tool_calls ----------

def _try_native_tool_calls(
    user_message: str,
    history: list[dict[str, str]],
    tool_map: dict[str, Any],
    tool_descriptions: str,
    tool_turns: list[ChatTurn],
    context: dict[str, Any],
) -> str | None:
    """尝试走 LangChain bind_tools / tool_calls 原生路径。

    若 chat 模型 / provider 不支持 bind_tools，返回 None，让调用方走回落路径。
    """
    if not llm_client.available:
        return None

    chat = _build_chat_client()
    if chat is None:
        return None

    try:
        # 用 LangChain 原生 API 绑定工具
        tools_list = list(tool_map.values())
        chat_with_tools = chat.bind_tools(tools_list)
    except Exception as exc:  # noqa: BLE001
        logger.info("bind_tools not supported, falling back", error=str(exc))
        return None

    messages = _build_langchain_messages(user_message, history, system=_SYSTEM_PROMPT)

    # Tool 循环
    loop_context = context.copy()
    for i in range(_MAX_TOOL_LOOPS):
        try:
            ai_msg = chat_with_tools.invoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("native tool_calls invoke failed", error=str(exc))
            return None

        # 读取 tool_calls（LangChain 0.1+ 在 AIMessage 上暴露 tool_calls 属性）
        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            # 模型直接回答
            content = getattr(ai_msg, "content", None) or str(ai_msg)
            return _strip_code_blocks(str(content))

        messages.append(ai_msg)

        for tc in tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            tool_name = str(name or "")
            if tool_name not in tool_map:
                logger.warning("unknown tool in tool_calls", name=tool_name)
                continue
            # args 可能是 dict / 字符串 / None，交给 invoke_tool 归一化处理
            if isinstance(args, dict):
                tool_kwargs = dict(args)
            elif isinstance(args, str) and args.strip():
                try:
                    tool_kwargs = json.loads(args)
                    if not isinstance(tool_kwargs, dict):
                        tool_kwargs = {"resume_text": str(args)}
                except json.JSONDecodeError:
                    tool_kwargs = {"resume_text": args}
            else:
                tool_kwargs = {}

            result = invoke_tool(tool_name, **tool_kwargs)

            result_str = str(result)
            truncated = _truncate(result_str, 400)
            tool_turns.append(ChatTurn(
                tool_name=str(name),
                tool_input=json.dumps(args, ensure_ascii=False),
                tool_output=result_str,
                truncated_output=truncated,
            ))
            # 缓存解析结果，避免重复调用解析
            if str(name) == "parse_resume_text":
                loop_context["parsed_resume_json"] = result_str

            messages.append({
                "role": "tool",
                "name": str(name),
                "content": result_str[:4000],
            })

    # 工具调用次数用完，用最后一条消息让模型给出总结
    try:
        ai_msg = chat_with_tools.invoke(messages)
        content = getattr(ai_msg, "content", None) or str(ai_msg)
        return _strip_code_blocks(str(content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("final answer invoke failed", error=str(exc))
        return None


# ---------- 路径 2：提示驱动的 tool selection ----------

def _run_prompt_based_tool_loop(
    user_message: str,
    history: list[dict[str, str]],
    tool_map: dict[str, Any],
    tool_descriptions: str,
    tool_turns: list[ChatTurn],
    context: dict[str, Any],
) -> str:
    """当原生 tool_calls 不可用时，用结构化提示让模型选择工具。

    模型输出中若包含 `[[TOOL: tool_name {json_args}]]` 标记，则调用工具；
    否则把整段文本当作自然语言答案返回。
    """
    loop_context = context.copy()

    for i in range(_MAX_TOOL_LOOPS):
        prompt = _build_prompt(user_message, history, tool_descriptions, loop_context, already_called=tool_turns)

        if llm_client.available:
            raw_reply = llm_client.invoke(prompt, system=_SYSTEM_PROMPT) or ""
        else:
            raw_reply = _heuristic_reply(user_message, loop_context)

        # 是否包含工具调用标记？
        tool_call = _extract_tool_call(raw_reply)
        if tool_call is None:
            return _strip_code_blocks(raw_reply) if raw_reply else "抱歉，我无法处理这个请求。"

        tool_name, tool_args = tool_call
        if tool_name not in tool_map:
            logger.warning("prompt-based: unknown tool", name=tool_name)
            return _strip_code_blocks(raw_reply)

        # 执行工具（用 invoke_tool，能自动归一化字段名）
        if isinstance(tool_args, dict):
            result = invoke_tool(tool_name, **tool_args)
        else:
            result = invoke_tool(tool_name, resume_text=str(tool_args))

        result_str = str(result)
        tool_turns.append(ChatTurn(
            tool_name=tool_name,
            tool_input=json.dumps(tool_args, ensure_ascii=False),
            tool_output=result_str,
            truncated_output=_truncate(result_str, 400),
        ))
        if tool_name == "parse_resume_text":
            loop_context["parsed_resume_json"] = result_str

        # 历史加一条「调用了 xx 工具，得到 ...」，让模型基于结果继续思考或给出最终答案
        history.append({"role": "assistant", "content": f"[调用了工具 {tool_name}，结果已写入上下文]"})
        user_message = f"（已调用工具 {tool_name}，其结果在上下文中）请基于工具结果给出最终回答。"

    # 循环上限
    return "分析已完成，但需要更多信息才能给出建议。请告诉我你关注的岗位或问题。"


# ---------- 辅助 ----------

def _build_chat_client():
    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # noqa: BLE001
        logger.warning("langchain_openai import failed", error=str(exc))
        return None
    try:
        return ChatOpenAI(
            model=llm_client.model,
            api_key=llm_client.api_key,
            base_url=llm_client.base_url,
            temperature=0.2,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ChatOpenAI init failed", error=str(exc))
        return None


def _build_langchain_messages(user_message: str, history: list[dict[str, str]], system: str | None = None) -> list[Any]:
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except Exception:  # noqa: BLE001
        return [{"role": "user", "content": user_message}]

    messages: list[Any] = []
    if system:
        messages.append(SystemMessage(content=system))
    for h in history[-10:]:  # 只保留最近 10 条
        role = (h.get("role") or "").lower()
        content = h.get("content") or ""
        if role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "user":
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=user_message))
    return messages


def _format_tool_descriptions(tools: list[Any]) -> str:
    lines = []
    for t in tools:
        name = getattr(t, "name", str(t))
        desc = getattr(t, "description", "")
        input_schema = getattr(t, "args_schema", None)
        args = ""
        if input_schema is not None:
            try:
                args = json.dumps(input_schema.model_json_schema(), ensure_ascii=False)
            except Exception:  # noqa: BLE001
                args = str(input_schema)
        lines.append(f"- [{name}] {desc}  参数 schema: {args}")
    return "\n".join(lines)


def _build_preamble(context: dict[str, Any]) -> str:
    preamble = []
    rt = context.get("resume_text")
    if rt:
        preamble.append(f"【附件 · 简历文本】\n{rt[:8000]}\n")
    jd = context.get("jd_text")
    if jd:
        preamble.append(f"【附件 · 岗位描述 (JD)】\n{jd[:8000]}\n")
    pr = context.get("parsed_resume_json")
    if pr:
        preamble.append(f"【上下文 · 已解析的简历结构】\n{pr[:2000]}\n")
    return "\n".join(preamble)


def _build_prompt(
    user_message: str,
    history: list[dict[str, str]],
    tool_descriptions: str,
    context: dict[str, Any],
    already_called: list[ChatTurn],
) -> str:
    history_text = "\n".join(
        f"{h['role']}: {h['content']}" for h in history[-6:]
    )
    # 给模型一个「可调用工具清单」和「当前附件上下文」
    return (
        f"【可调用工具清单】\n{tool_descriptions}\n\n"
        f"【对话历史（最近几条）】\n{history_text}\n\n"
        f"【用户当前消息】\n{user_message}\n\n"
        f"已调用过的工具（无需重复调用同样参数）："
        f"{', '.join(t.tool_name for t in already_called) or '(无)'}\n\n"
        "请思考：是否需要调用工具？\n"
        "- 若无需调用工具，直接用自然语言回答用户。\n"
        "- 若需要调用某个工具，**整段回复中只输出**一行如下格式（不要其他内容）：\n"
        '    [[TOOL: tool_name {"param": "value", ...}]]\n'
        "注意：\n"
        "  * tool_name 必须来自上面的「可调用工具清单」；\n"
        "  * JSON 必须合法（字符串用双引号，参数名与工具 schema 保持一致）；\n"
        "  * 一次只调用一个工具，工具返回后你会有机会决定下一步。\n"
        "- 参数来源：如果用户上传了简历/JD（在「附件」里），你可以把对应文本作为参数传入。"
    )


def _extract_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """从模型自由文本中解析 `[[TOOL: name {json}]]` 标记。"""
    if not text:
        return None
    m = re.search(r"\[\[TOOL\s*:\s*(\w+)\s*(\{.*?\})\]\]", text, flags=re.DOTALL)
    if not m:
        return None
    name = m.group(1)
    try:
        args = json.loads(m.group(2))
    except json.JSONDecodeError:
        return None
    return name, args


def _heuristic_reply(user_message: str, context: dict[str, Any]) -> str:
    """LLM 未配置时的简单回落：基于附件给出启发式回答。"""
    has_resume = bool(context.get("resume_text"))
    has_jd = bool(context.get("jd_text"))
    if has_resume and has_jd:
        return (
            "已收到你的简历和 JD。当前 LLM 未配置，只能做基础提示：\n"
            "1. 请把简历中与 JD 关键词最契合的技能和项目前置；\n"
            "2. 为每段经历加上「动作动词 + 具体成果」式描述；\n"
            "3. 移除与岗位无关的内容，控制在 1-2 页。\n"
            "如需要更细致的建议，请先在后端配置 LLM API Key。"
        )
    if has_resume:
        return (
            "已收到简历文本。建议你同时提供目标岗位描述（JD），我才能给出更有针对性的建议；"
            "或告诉我你希望关注的岗位/方向。（当前 LLM 未配置，以上为基础提示。）"
        )
    return (
        "你好！我是简历小助手。请提供简历或岗位描述文本，我会帮你解析/匹配/优化。"
        "（当前 LLM 未配置，以上为基础提示。）"
    )


def _strip_code_blocks(text: str) -> str:
    """去掉模型偶尔输出的 ```json ... ``` 包裹。"""
    if not text:
        return text
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
        # 去掉第一行的 json / json5 / js 标签
        first, _, rest = text.partition("\n")
        if first.strip().lower() in {"json", "json5", "js", "javascript", ""}:
            text = rest.strip()
    return text


def _truncate(s: str, limit: int) -> str:
    if not s:
        return ""
    return s if len(s) <= limit else s[:limit] + "..."
