"""对话相关 API：聊天 + 文件上传 + 多轮会话 + 长期记忆。

阶段 7：
- 对话落库（ConversationORM/MessageORM），支持 session_id 续聊、刷新/重启不丢；
- 每轮召回长期记忆注入 Agent，并在回答后抽取新记忆存库；
- 新增会话列表/详情/删除、记忆查看端点。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.chat_agent import run_agent
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.schemas import ConversationDetailOut, ConversationOut, MemoryOut, MessageOut
from app.services import conversation_repository as conv_repo
from app.services import memory_service
from app.services.resume_parser import extract_text

logger = get_logger("api.chat")
router = APIRouter()


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"无效的 ID: {value}") from None


@router.post("", summary="发送一条聊天消息，由 Agent 决定是否调用工具")
async def chat_message(
    message: str = Form(..., description="用户发送的消息文本"),
    resume_file: UploadFile | None = File(None, description="可选：上传一份简历（PDF/Word/TXT/MD/图片），文本作为附件上下文"),
    jd_file: UploadFile | None = File(None, description="可选：上传一份岗位描述（PDF/Word/TXT/MD/图片），文本作为附件上下文"),
    history: str | None = Form(None, description="可选：前端传入的历史（兜底；优先用 DB 中该会话历史）"),
    user_role: str = Form("recruiter", description="用户身份：recruiter（默认）或 candidate"),
    user_id: str = Form("anonymous", description="用户标识，本期默认 anonymous，为将来登录系统预留"),
    session_id: str | None = Form(None, description="会话 ID（conversation id）。不传则新建会话"),
    db: Session = Depends(get_db),
) -> dict:
    """单轮聊天接口，带会话持久化与长期记忆。"""
    uid = (user_id or "anonymous").strip() or "anonymous"

    # 0) 解析 / 新建会话
    if session_id:
        conv = conv_repo.get_conversation(db, _parse_uuid(session_id))
        if conv is None:
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        title = message.strip()[:30] or "新会话"
        conv = conv_repo.create_conversation(db, user_id=uid, title=title)

    # 1) 读取附件文本
    context: dict[str, object] = {}
    if resume_file is not None and resume_file.filename:
        try:
            suffix = resume_file.filename.rsplit(".", 1)[-1].lower()
            context["resume_text"] = extract_text(await resume_file.read(), suffix)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"读取简历文件失败: {exc}") from exc
    if jd_file is not None and jd_file.filename:
        try:
            suffix = jd_file.filename.rsplit(".", 1)[-1].lower()
            context["jd_text"] = extract_text(await jd_file.read(), suffix)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"读取 JD 文件失败: {exc}") from exc

    # 2) 历史：优先用 DB 中该会话的消息（落库后即为单一事实源），前端 history 仅兜底
    db_messages = conv_repo.get_messages(db, conv.id, limit=20)
    if db_messages:
        history_objs = [{"role": m.role, "content": m.content or ""} for m in db_messages[-10:]]
    else:
        history_objs = _parse_history(history)

    # 3) 召回长期记忆
    recalled = memory_service.recall_memories(db, user_id=uid, query=message)

    # 4) 落库用户消息
    conv_repo.add_message(db, conv_id=conv.id, role="user", content=message)

    # 5) 跑 Agent
    try:
        reply = run_agent(
            user_message=message,
            context=context,
            history=history_objs,
            user_role=user_role,
            recalled_memories=recalled,
        )
    except Exception as exc:  # noqa: BLE001
        db.commit()  # 至少保住用户消息与会话
        logger.exception("agent run failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {exc}") from exc

    # 6) 落库助手消息
    tool_calls_payload = [
        {
            "tool_name": t.tool_name,
            "tool_input": t.tool_input,
            "tool_output": t.tool_output,
            "truncated_output": t.truncated_output,
        }
        for t in reply.tool_calls
    ]
    conv_repo.add_message(
        db, conv_id=conv.id, role="assistant", content=reply.answer, tool_calls=tool_calls_payload
    )

    # 7) 抽取并保存长期记忆（同步；生产可异步/后台队列）
    try:
        new_memories = memory_service.extract_memories(message, reply.answer, reply.user_role)
        memory_service.save_memories(
            db, user_id=uid, memories=new_memories, source_session=str(conv.id)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory extract/save failed", error=str(exc))

    db.commit()

    return {
        "answer": reply.answer,
        "tool_calls": tool_calls_payload,
        "used_tools": reply.used_tools,
        "provider": reply.provider,
        "user_role": reply.user_role,
        "session_id": str(conv.id),
        "recalled_memories": recalled,
    }


# ---------------- 会话管理端点 ----------------

@router.get("/conversations", response_model=list[ConversationOut], summary="按用户列出会话")
async def list_conversations(
    user_id: str = "anonymous", db: Session = Depends(get_db)
) -> list[ConversationOut]:
    convs = conv_repo.list_conversations(db, user_id=(user_id or "anonymous"))
    return [ConversationOut.model_validate(c) for c in convs]


@router.get("/conversations/{conv_id}", response_model=ConversationDetailOut, summary="会话详情 + 消息")
async def get_conversation(conv_id: str, db: Session = Depends(get_db)) -> ConversationDetailOut:
    cid = _parse_uuid(conv_id)
    conv = conv_repo.get_conversation(db, cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    detail = ConversationDetailOut.model_validate(conv)
    detail.messages = [
        MessageOut.model_validate(m) for m in conv_repo.get_messages(db, cid)
    ]
    return detail


@router.delete("/conversations/{conv_id}", summary="删除会话")
async def delete_conversation(conv_id: str, db: Session = Depends(get_db)) -> dict:
    ok = conv_repo.delete_conversation(db, _parse_uuid(conv_id))
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.commit()
    return {"deleted": conv_id}


@router.get("/memories", response_model=list[MemoryOut], summary="查看某用户的长期记忆")
async def list_memories(user_id: str = "anonymous", db: Session = Depends(get_db)) -> list[MemoryOut]:
    rows = memory_service.list_memories_by_user(db, user_id or "anonymous")
    return [MemoryOut.model_validate(m) for m in rows]


# ---------------- helper ----------------

def _parse_history(history: str | None) -> list[dict[str, str]]:
    if not history:
        return []
    import json as _json

    try:
        parsed = _json.loads(history)
    except _json.JSONDecodeError:
        return []
    out: list[dict[str, str]] = []
    if isinstance(parsed, list):
        for h in parsed:
            if isinstance(h, dict) and h.get("role") in {"user", "assistant"} and h.get("content"):
                out.append({"role": h["role"], "content": h["content"]})
    return out
