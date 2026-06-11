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


__all__ = ["ResumeORM", "MatchResultORM"]
