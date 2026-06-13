"""SQLAlchemy ORM 数据模型。

注意：在阶段 2 前，数据库尚未启用，这些模型留作后续接入。
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON

from app.core.database import Base

# 兼容 SQLite，用 JSON；PostgreSQL 时优先 JSONB
_JSON = JSON().with_variant(JSONB(), "postgresql")


class ResumeORM(Base):
    """简历数据表。"""

    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    filename = Column(String(512), nullable=True)
    file_hash = Column(String(128), unique=True, nullable=True, index=True)
    raw_text = Column(Text, nullable=True)
    name = Column(String(128), nullable=True)
    email = Column(String(256), nullable=True)
    phone = Column(String(64), nullable=True)
    education_level = Column(String(64), nullable=True)
    years_of_experience = Column(Float, nullable=True)
    skills = Column(_JSON, default=list)
    work_history = Column(_JSON, default=list)
    projects = Column(_JSON, default=list)
    parse_confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MatchResultORM(Base):
    """匹配结果数据表。"""

    __tablename__ = "match_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    resume_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    jd_text = Column(Text, nullable=True)
    overall_score = Column(Float, default=0.0)
    skill_match = Column(Float, default=0.0)
    experience_match = Column(Float, default=0.0)
    education_match = Column(Float, default=0.0)
    strengths = Column(_JSON, default=list)
    gaps = Column(_JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------- 阶段 7：Agent 记忆系统 ----------------

class ConversationORM(Base):
    """会话表（情景记忆 / A）。一个 conversation 是一段多轮对话。"""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # user_id 本期默认 "anonymous"，为将来登录系统预留。
    user_id = Column(String(128), nullable=False, default="anonymous", index=True)
    title = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MessageORM(Base):
    """消息表（会话内的每一条 user / assistant 消息）。"""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=True)
    tool_calls = Column(_JSON, default=list)  # assistant 消息的工具调用记录
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryORM(Base):
    """长期语义记忆表（C）。跨会话记住用户画像 / 关键事实。"""

    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(128), nullable=False, default="anonymous", index=True)
    kind = Column(String(32), nullable=False, default="fact")  # profile | fact | preference
    content = Column(Text, nullable=False)
    source_session = Column(String(64), nullable=True)  # 来源会话 id（字符串存，便于追溯）
    created_at = Column(DateTime, default=datetime.utcnow)


__all__ = [
    "ResumeORM",
    "MatchResultORM",
    "ConversationORM",
    "MessageORM",
    "MemoryORM",
]
