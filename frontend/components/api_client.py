"""后端 API 客户端封装。"""
from __future__ import annotations

from typing import Any

import requests


class APIClient:
    """统一 API 客户端，供所有 Streamlit 页面共用。"""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = 30

    # ---------- 通用 ----------

    def health_check(self) -> tuple[bool, str]:
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            resp.raise_for_status()
            return True, resp.json().get("service", "ok")
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    # ---------- 简历 ----------

    def upload_resume(self, file_bytes: bytes, filename: str) -> dict[str, Any] | None:
        try:
            files = {"file": (filename, file_bytes)}
            resp = requests.post(
                f"{self.base_url}/api/v1/resumes/upload",
                files=files,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def list_resumes(self) -> list[dict[str, Any]]:
        try:
            resp = requests.get(f"{self.base_url}/api/v1/resumes", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json() or []
        except Exception:  # noqa: BLE001
            return []


# 全局单例
api = APIClient()
