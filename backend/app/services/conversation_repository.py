"""会话 / 消息数据访问层（情景记忆 A）。

模块级函数，第一参收 ``session``，不负责事务边界（commit 由 API 层控制），
与 resume_repository.py 风格一致。
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.database import ConversationORM, MessageORM

logger = get_logger("conversation_repository")


def create_conversation(
    session: Session, *, user_id: str = "anonymous", title: str | None = None
) -> ConversationORM:
    conv = ConversationORM(user_id=user_id or "anonymous", title=title)
    session.add(conv)
    session.flush()  # 触发 id 生成
    return conv


def get_conversation(session: Session, conv_id: UUID) -> ConversationORM | None:
    return session.get(ConversationORM, conv_id)


def list_conversations(
    session: Session, *, user_id: str = "anonymous", limit: int = 50
) -> list[ConversationORM]:
    return list(
        session.scalars(
            select(ConversationORM)
            .where(ConversationORM.user_id == (user_id or "anonymous"))
            .order_by(ConversationORM.updated_at.desc())
            .limit(limit)
        )
    )


def add_message(
    session: Session,
    *,
    conv_id: UUID,
    role: str,
    content: str,
    tool_calls: list[dict] | None = None,
) -> MessageORM:
    msg = MessageORM(
        conversation_id=conv_id,
        role=role,
        content=content or "",
        tool_calls=tool_calls or [],
    )
    session.add(msg)
    session.flush()
    return msg


def get_messages(session: Session, conv_id: UUID, limit: int = 100) -> list[MessageORM]:
    return list(
        session.scalars(
            select(MessageORM)
            .where(MessageORM.conversation_id == conv_id)
            .order_by(MessageORM.created_at.asc())
            .limit(limit)
        )
    )


def delete_conversation(session: Session, conv_id: UUID) -> bool:
    conv = session.get(ConversationORM, conv_id)
    if conv is None:
        return False
    # 一并删除其消息
    for msg in get_messages(session, conv_id, limit=10000):
        session.delete(msg)
    session.delete(conv)
    session.flush()
    return True


__all__ = [
    "create_conversation",
    "get_conversation",
    "list_conversations",
    "add_message",
    "get_messages",
    "delete_conversation",
]
