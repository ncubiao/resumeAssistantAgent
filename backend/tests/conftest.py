"""pytest 根目录配置：PYTHONPATH + 测试数据库隔离。"""
import sys
from pathlib import Path

import pytest

# 把 backend 目录加入 PYTHONPATH，便于 pytest 直接运行
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """每个测试用独立的临时文件 SQLite，避免污染默认 resume_agent.db。

    关键点：
    - 用临时**文件**而非 ``:memory:``——TestClient 多线程下 in-memory 库每连接独立会丢表。
    - 重置 database 模块的懒加载全局（_engine / _SessionLocal），让 get_db 用新 URL 重建。
      get_db 在调用时才读 _SessionLocal，所以重置后无需额外覆盖依赖。
    """
    from app.core import database

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(database.settings, "database_url", db_url)
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_SessionLocal", None)

    database.init_db()
    yield
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_SessionLocal", None)
