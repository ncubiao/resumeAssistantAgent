"""对话相关 API：聊天 + 文件上传 + 多轮会话。"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.chat_agent import run_agent
from app.core.logging import get_logger
from app.services.resume_parser import extract_text

logger = get_logger("api.chat")
router = APIRouter()


class ChatToolTurn:
    """仅用于接口序列化，不做 Pydantic 模型。"""


@router.post("", summary="发送一条聊天消息，由 Agent 决定是否调用工具")
async def chat_message(
    message: str = Form(..., description="用户发送的消息文本"),
    resume_file: UploadFile | None = File(None, description="可选：上传一份简历（PDF/Word/TXT/MD/图片PNG/JPG/WEBP/BMP/GIF），其文本会作为附件上下文提供给 Agent"),
    jd_file: UploadFile | None = File(None, description="可选：上传一份岗位描述（PDF/Word/TXT/MD/图片PNG/JPG/WEBP/BMP/GIF），其文本会作为附件上下文提供给 Agent"),
    history: str | None = Form(None, description="可选：之前的对话历史，JSON 数组，每项 {\"role\": \"user\"|\"assistant\", \"content\": \"...\"}"),
) -> dict:
    """单轮聊天接口。

    - 支持在发送消息时附带文件（简历 / JD）；
    - 后端提取文件文本后，交给 Agent 决定是否调用解析/匹配/优化工具；
    - 返回自然语言答案 + 工具调用过程（方便前端展示「思考过程」）。
    """
    context: dict[str, object] = {}

    # 1) 读取并提取简历文件文本
    if resume_file is not None and resume_file.filename:
        try:
            suffix = resume_file.filename.rsplit(".", 1)[-1].lower()
            raw_bytes = await resume_file.read()
            context["resume_text"] = extract_text(raw_bytes, suffix)
            logger.info(
                "resume file attached",
                filename=resume_file.filename,
                size=len(raw_bytes),
                text_len=len(str(context["resume_text"])),
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"读取简历文件失败: {exc}") from exc

    # 2) 读取并提取 JD 文件文本
    if jd_file is not None and jd_file.filename:
        try:
            suffix = jd_file.filename.rsplit(".", 1)[-1].lower()
            raw_bytes = await jd_file.read()
            context["jd_text"] = extract_text(raw_bytes, suffix)
            logger.info(
                "jd file attached",
                filename=jd_file.filename,
                size=len(raw_bytes),
                text_len=len(str(context["jd_text"])),
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"读取 JD 文件失败: {exc}") from exc

    # 3) 解析 history（如果提供）
    history_objs: list[dict[str, str]] = []
    if history:
        import json as _json

        try:
            parsed = _json.loads(history)
            if isinstance(parsed, list):
                for h in parsed:
                    if isinstance(h, dict) and h.get("role") in {"user", "assistant"} and h.get("content"):
                        history_objs.append({"role": h["role"], "content": h["content"]})
        except _json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"history 不是合法 JSON: {exc}") from exc

    # 4) 交给 Agent
    try:
        reply = run_agent(user_message=message, context=context, history=history_objs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent run failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {exc}") from exc

    return {
        "answer": reply.answer,
        "tool_calls": [
            {
                "tool_name": t.tool_name,
                "tool_input": t.tool_input,
                "tool_output": t.tool_output,
                "truncated_output": t.truncated_output,
            }
            for t in reply.tool_calls
        ],
        "used_tools": reply.used_tools,
        "provider": reply.provider,
    }
