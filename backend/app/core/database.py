"""数据库连接管理与 SQLAlchemy Session。"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("db")

Base = declarative_base()

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
            connect_args=connect_args,
        )
        logger.info("database engine created", url=settings.database_url)
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_get_engine(),
            future=True,
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用数据库 Session。"""
    session = _get_session_local()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope():
    """脚本/测试中使用的 Session 上下文管理器。"""
    session = _get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """初始化数据库表结构。"""
    # 触发 ORM 模型注册
    from app.models import database as _  # noqa: F401

    Base.metadata.create_all(bind=_get_engine())
    logger.info("database tables initialized")
