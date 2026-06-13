"""长期语义记忆服务（C）。

三件事：
1. extract_memories：从一轮对话抽取"值得长期记住的事实/画像"（LLM 抽取，无 LLM 则跳过）
2. save_memories：落库 + 向量化入独立的记忆 FAISS 索引（与简历索引隔离）
3. recall_memories：按 user_id 语义召回相关记忆（无 embedding 则时间序兜底）

设计：记忆向量索引用独立的 VectorStore 实例（不同 index_path），metadata 存
{"memory_id", "user_id"}，search 后必须按 user_id 过滤避免串户。
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.database import MemoryORM
from app.services.embedding import embedding_client
from app.services.vector_store import VectorStore
from app.utils.llm_client import llm_client

logger = get_logger("memory_service")

# 独立的记忆向量索引（与简历索引隔离，避免语义空间污染）
memory_store = VectorStore(index_path=settings.memory_index_path)


# ---------------- 抽取 ----------------

_EXTRACT_SYSTEM = (
    "你是一个对话记忆抽取器。从一轮对话中抽取**值得长期记住**的、关于用户的稳定事实，"
    "如：求职者的目标岗位 / 技能短板 / 职业偏好；招聘方在招的岗位 / 用人偏好。"
    "忽略寒暄、一次性问题、临时上下文。输出必须是合法 JSON，无 Markdown。"
)


def extract_memories(user_message: str, assistant_answer: str, user_role: str) -> list[dict]:
    """抽取记忆条目。返回 [{"kind": "profile|fact|preference", "content": "..."}]。

    LLM 不可用时返回 []（优雅降级，不塞启发式噪声）。
    """
    if not settings.memory_enabled or not llm_client.available:
        return []

    role_hint = "求职者" if user_role == "candidate" else "招聘方"
    prompt = (
        f"对话角色：{role_hint}\n"
        f"用户说：{(user_message or '')[:1500]}\n"
        f"助手答：{(assistant_answer or '')[:1500]}\n\n"
        "请抽取 0-3 条值得长期记住的事实。JSON 结构：\n"
        '{"memories": [{"kind": "profile|fact|preference", "content": "一句话事实"}]}\n'
        "若没有值得记的，返回 {\"memories\": []}。只输出 JSON。"
    )
    data = llm_client.invoke_json(prompt=prompt, system=_EXTRACT_SYSTEM, default={"memories": []})
    items = data.get("memories") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    out: list[dict] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("content") or "").strip():
            kind = str(it.get("kind") or "fact").strip().lower()
            if kind not in {"profile", "fact", "preference"}:
                kind = "fact"
            out.append({"kind": kind, "content": str(it["content"]).strip()})
    return out[:3]


# ---------------- 存储 ----------------

def save_memories(
    session: Session, *, user_id: str, memories: list[dict], source_session: str | None = None
) -> list[MemoryORM]:
    """落库 + 向量化。按 (user_id, content) 精确去重，避免反复抽取重复入库。"""
    if not memories:
        return []

    existing = {
        m.content
        for m in session.scalars(
            select(MemoryORM).where(MemoryORM.user_id == user_id)
        )
    }

    created: list[MemoryORM] = []
    new_texts: list[str] = []
    for mem in memories:
        content = mem["content"]
        if content in existing:
            continue
        orm = MemoryORM(
            user_id=user_id,
            kind=mem.get("kind", "fact"),
            content=content,
            source_session=source_session,
        )
        session.add(orm)
        created.append(orm)
        new_texts.append(content)
        existing.add(content)

    if not created:
        return []
    session.flush()  # 拿到 id

    # 向量化入记忆索引（embedding 不可用时跳过，召回会走时间序兜底）
    if embedding_client.available and new_texts:
        vectors = embedding_client.embed_texts(new_texts)
        if vectors is not None:
            meta = [{"memory_id": str(o.id), "user_id": user_id} for o in created]
            try:
                memory_store.add(vectors, meta)
                memory_store.save()
            except Exception as exc:  # noqa: BLE001
                logger.warning("memory vector index update failed", error=str(exc))

    logger.info("memories saved", user_id=user_id, count=len(created))
    return created


# ---------------- 召回 ----------------

def recall_memories(session: Session, *, user_id: str, query: str, k: int | None = None) -> list[str]:
    """召回该用户的相关记忆 content 列表。

    embedding 可用：语义检索（search 后按 user_id 过滤）。
    否则：取该用户最近 k 条（时间序兜底）。
    """
    if not settings.memory_enabled:
        return []
    k = k or settings.memory_recall_k

    if embedding_client.available and memory_store.size() > 0:
        qv = embedding_client.embed_query(query or "")
        if qv is not None:
            # 多取一些再按 user_id 过滤
            hits = memory_store.search(qv, k=k * 4)
            mem_ids: list[UUID] = []
            for hit in hits:
                if hit.get("user_id") != user_id:
                    continue
                try:
                    mem_ids.append(UUID(str(hit.get("memory_id"))))
                except (ValueError, TypeError):
                    continue
                if len(mem_ids) >= k:
                    break
            if mem_ids:
                rows = session.scalars(
                    select(MemoryORM).where(MemoryORM.id.in_(mem_ids))
                ).all()
                # 保持 FAISS 相似度顺序
                by_id = {o.id: o for o in rows}
                return [by_id[mid].content for mid in mem_ids if mid in by_id]

    # 兜底：时间序最近 k 条
    rows = session.scalars(
        select(MemoryORM)
        .where(MemoryORM.user_id == user_id)
        .order_by(MemoryORM.created_at.desc())
        .limit(k)
    ).all()
    return [r.content for r in rows]


def list_memories_by_user(session: Session, user_id: str, limit: int = 100) -> list[MemoryORM]:
    return list(
        session.scalars(
            select(MemoryORM)
            .where(MemoryORM.user_id == user_id)
            .order_by(MemoryORM.created_at.desc())
            .limit(limit)
        )
    )


__all__ = [
    "memory_store",
    "extract_memories",
    "save_memories",
    "recall_memories",
    "list_memories_by_user",
]
