"""简历相关 API 路由。"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.nodes.parser_agent import run as run_parser
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.schemas import ResumeOut, ResumeUpdate
from app.services import resume_repository as repo
from app.services.embedding import embedding_client
from app.services.resume_parser import extract_text
from app.services.vector_store import vector_store
from app.utils.helpers import compute_file_hash

logger = get_logger("api.resume")
router = APIRouter()

_SUPPORTED_SUFFIXES = {"pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"}


class ParseTextRequest(BaseModel):
    text: str


class SearchRequest(BaseModel):
    query: str
    k: int = 5


# ---------- 写入：上传 / 解析 ----------

@router.post(
    "/upload",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传并解析简历（PDF/Word/TXT/图片），落库 + 去重",
)
async def upload_resume(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> ResumeOut:
    """上传简历文件 -> 提取文本 -> Parser Agent 结构化 -> 落库（按内容 hash 去重）。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="无效文件名")

    suffix = file.filename.rsplit(".", 1)[-1].lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 .{suffix}（支持 {', '.join(sorted(_SUPPORTED_SUFFIXES))}）",
        )

    logger.info("processing resume upload", filename=file.filename, suffix=suffix)

    contents = await file.read()
    file_hash = compute_file_hash(contents)

    existing = repo.get_by_hash(db, file_hash)
    if existing is not None:
        # 去重幂等：相同内容已存在，直接返回已有记录
        logger.info("resume dedup hit", resume_id=str(existing.id), filename=file.filename)
        return ResumeOut.model_validate(existing)

    raw_text = extract_text(contents, suffix)
    return _persist_resume(db, file.filename, raw_text, file_hash)


@router.post(
    "/parse-text",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
    summary="直接传入简历文本进行解析并落库",
)
async def parse_text(
    payload: ParseTextRequest, db: Session = Depends(get_db)
) -> ResumeOut:
    """方便调试 / 测试：直接上传简历文本内容。"""
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")

    file_hash = compute_file_hash(payload.text.encode("utf-8"))
    existing = repo.get_by_hash(db, file_hash)
    if existing is not None:
        return ResumeOut.model_validate(existing)

    return _persist_resume(db, "plain_text.txt", payload.text, file_hash)


# ---------- 读取 / 更新 / 删除 ----------

@router.get("", response_model=list[ResumeOut], summary="获取简历列表")
async def list_resumes(db: Session = Depends(get_db)) -> list[ResumeOut]:
    return [ResumeOut.model_validate(o) for o in repo.list_resumes(db)]


@router.post(
    "/search",
    response_model=list[ResumeOut],
    summary="语义检索简历（无 embedding 时降级为关键词检索）",
)
async def search_resumes(
    payload: SearchRequest, db: Session = Depends(get_db)
) -> list[ResumeOut]:
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")
    k = max(1, min(payload.k, 50))

    if embedding_client.available:
        qv = embedding_client.embed_query(query)
        if qv is not None:
            hits = vector_store.search(qv, k=k)
            results: list[ResumeOut] = []
            for hit in hits:
                rid = hit.get("resume_id")
                if not rid:
                    continue
                try:
                    orm = repo.get_by_id(db, UUID(str(rid)))
                except ValueError:
                    orm = None
                # lazy cleanup：FAISS 残留但 DB 已删的记录直接跳过
                if orm is not None:
                    results.append(ResumeOut.model_validate(orm))
            return results

    # 降级：关键词检索
    logger.info("search falling back to keyword match", query_len=len(query))
    return [ResumeOut.model_validate(o) for o in repo.keyword_search(db, query, k)]


@router.get("/{resume_id}", response_model=ResumeOut, summary="获取简历详情")
async def get_resume(resume_id: str, db: Session = Depends(get_db)) -> ResumeOut:
    orm = repo.get_by_id(db, _parse_uuid(resume_id))
    if orm is None:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeOut.model_validate(orm)


@router.put("/{resume_id}", response_model=ResumeOut, summary="更新简历信息")
async def update_resume(
    resume_id: str, payload: ResumeUpdate, db: Session = Depends(get_db)
) -> ResumeOut:
    orm = repo.update_resume(db, _parse_uuid(resume_id), payload)
    if orm is None:
        raise HTTPException(status_code=404, detail="简历不存在")
    db.commit()
    db.refresh(orm)
    return ResumeOut.model_validate(orm)


@router.delete("/{resume_id}", status_code=200, summary="删除简历")
async def delete_resume(resume_id: str, db: Session = Depends(get_db)) -> dict:
    ok = repo.delete_resume(db, _parse_uuid(resume_id))
    if not ok:
        raise HTTPException(status_code=404, detail="简历不存在")
    db.commit()
    # 注：FAISS 向量不在此处删除（IndexFlatL2 不支持删单条），search 时按 DB 存在性过滤
    return {"deleted": resume_id}


# ---------- 内部 helper ----------

def _persist_resume(
    db: Session, filename: str, raw_text: str, file_hash: str
) -> ResumeOut:
    """解析 -> 落库 -> 同步向量索引，返回 ResumeOut。"""
    parsed, confidence = _parse(raw_text)
    orm = repo.create_resume(
        db,
        filename=filename,
        file_hash=file_hash,
        raw_text=raw_text,
        parsed=parsed,
        parse_confidence=confidence,
    )
    db.commit()
    db.refresh(orm)

    _index_resume(orm.id, raw_text, parsed)

    logger.info(
        "resume persisted",
        resume_id=str(orm.id),
        filename=filename,
        confidence=confidence,
        skills_count=len(parsed.get("skills") or []),
    )
    return ResumeOut.model_validate(orm)


def _parse(raw_text: str) -> tuple[dict[str, Any], float]:
    """调用 Parser Agent，分离"解析"与"落库"两个关注点。"""
    parser_result: dict[str, Any] = run_parser(raw_text) or {}
    parsed = parser_result.get("parsed_resume") or {}
    confidence = float(parser_result.get("parse_confidence") or 0.0)
    return parsed, confidence


def _index_resume(resume_id: UUID, raw_text: str, parsed: dict) -> None:
    """把简历向量写入 FAISS（embedding 不可用时静默跳过）。"""
    if not embedding_client.available:
        return
    skills = " ".join(str(s) for s in (parsed.get("skills") or []))
    doc = f"{raw_text}\n{skills}".strip()
    vectors = embedding_client.embed_texts([doc])
    if vectors is None:
        return
    try:
        vector_store.add(vectors, [{"resume_id": str(resume_id)}])
        vector_store.save()
    except Exception as exc:  # noqa: BLE001
        logger.warning("vector index update failed", error=str(exc))


def _parse_uuid(resume_id: str) -> UUID:
    try:
        return UUID(resume_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="无效的简历 ID（应为 UUID）") from None
