"""数据库初始化脚本。

阶段 2 才会真正启用数据库，但脚本已提前准备好。

用法:
    cd backend && python -m app.core.init_db
    或在项目根目录: python -m backend.app.core.init_db
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 backend 目录加入 sys.path 以便导入
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import init_db  # noqa: E402
from app.core.logging import get_logger  # noqa: E402

logger = get_logger("init_db")


def main() -> None:
    logger.info("initializing database...")
    init_db()
    logger.info("database initialized successfully")


if __name__ == "__main__":
    main()
