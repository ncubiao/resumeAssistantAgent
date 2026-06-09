"""pytest 根目录标记。"""
import sys
from pathlib import Path

# 把 backend 目录加入 PYTHONPATH，便于 pytest 直接运行
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
