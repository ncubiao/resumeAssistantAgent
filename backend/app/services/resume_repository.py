"""简历数据访问层（Repository）。

集中所有 ResumeORM 的数据库读写，让 API 层不直接接触 ORM 查询，保持分层清晰。

约定：
- 所有函数第一个参数为 ``session``，**不负责** session 的生命周期与事务边界
  （commit/rollback/close 由调用方控制，见 API 层的 ``Depends(get_db)``）。
- ``resume_id`` 统一使用 ``UUID`` 类型，str -> UUID 的转换在 API 层完成。
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.database import ResumeORM
from app.models.schemas import ResumeUpdate

logger = get_logger("resume_repository")


def create_resume(
    session: Session,
    *,
    filename: str | None,
    file_hash: str | None,
    raw_text: str,
    parsed: dict,
    parse_confidence: float,
) -> ResumeORM:
    """新建一条简历记录（不 commit，由调用方决定事务）。"""
    orm = ResumeORM(
        filename=filename,
        file_hash=file_hash,
        raw_text=raw_text,
        name=parsed.get("name"),
        email=parsed.get("email"),
        phone=parsed.get("phone"),
        education_level=parsed.get("education_level"),
        years_of_experience=_to_float(parsed.get("years_of_experience")),
        skills=parsed.get("skills") or [],
        work_history=parsed.get("work_history") or [],
        projects=parsed.get("projects") or [],
        parse_confidence=parse_confidence,
    )
    session.add(orm)
    session.flush()  # 触发 default 生成 id，便于调用方拿到主键
    return orm


def get_by_hash(session: Session, file_hash: str) -> ResumeORM | None:
    if not file_hash:
        return None
    return session.scalars(
        select(ResumeORM).where(ResumeORM.file_hash == file_hash)
    ).first()


def get_by_id(session: Session, resume_id: UUID) -> ResumeORM | None:
    return session.get(ResumeORM, resume_id)


def list_resumes(session: Session, *, limit: int = 100, offset: int = 0) -> list[ResumeORM]:
    return list(
        session.scalars(
            select(ResumeORM)
            .order_by(ResumeORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def update_resume(
    session: Session, resume_id: UUID, payload: ResumeUpdate
) -> ResumeORM | None:
    orm = session.get(ResumeORM, resume_id)
    if orm is None:
        return None
    # 只更新显式传入的字段（exclude_unset），避免把未提供的字段覆盖为 None
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        # work_history 等嵌套模型 model_dump 后已是 list[dict]，可直接存 JSON 列
        setattr(orm, field, value)
    session.flush()
    return orm


def delete_resume(session: Session, resume_id: UUID) -> bool:
    orm = session.get(ResumeORM, resume_id)
    if orm is None:
        return False
    session.delete(orm)
    session.flush()
    return True


def keyword_search(session: Session, query: str, k: int) -> list[ResumeORM]:
    """无 embedding 时的降级检索：按 query 分词在 raw_text 上计数打分取 top-k。

    SQLite/PostgreSQL 通用：用 LIKE 逐词命中计数，命中越多排名越前。
    刻意保持简单——它只是 embedding 不可用时的兜底，不追求召回质量。
    """
    tokens = _tokenize(query)
    if not tokens:
        return []

    candidates = list(session.scalars(select(ResumeORM)))
    scored: list[tuple[int, ResumeORM]] = []
    for orm in candidates:
        haystack = (orm.raw_text or "").lower()
        # 技能字段也纳入匹配，提升命中率
        haystack += " " + " ".join(str(s).lower() for s in (orm.skills or []))
        score = sum(1 for t in tokens if t in haystack)
        if score > 0:
            scored.append((score, orm))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [orm for _, orm in scored[:k]]


# ---------------- 辅助 ----------------

def _tokenize(text: str) -> list[str]:
    """极简分词：按非字母数字切分 + 保留长度 >=2 的词，去重。中英文混排够用。"""
    import re

    raw = re.split(r"[^0-9a-zA-Z一-鿿]+", (text or "").lower())
    seen: list[str] = []
    for tok in raw:
        if len(tok) >= 2 and tok not in seen:
            seen.append(tok)
    return seen


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return None


__all__ = [
    "create_resume",
    "get_by_hash",
    "get_by_id",
    "list_resumes",
    "update_resume",
    "delete_resume",
    "keyword_search",
]
