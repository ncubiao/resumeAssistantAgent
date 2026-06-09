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

    # ---------- 聊天 Agent ----------

    def chat(
        self,
        message: str,
        resume_file: bytes | None = None,
        resume_filename: str | None = None,
        jd_file: bytes | None = None,
        jd_filename: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        try:
            data = {"message": message}
            if history:
                import json as _json

                data["history"] = _json.dumps(history)
            files: dict[str, tuple[str, bytes]] = {}
            if resume_file is not None and resume_filename:
                files["resume_file"] = (resume_filename, resume_file)
            if jd_file is not None and jd_filename:
                files["jd_file"] = (jd_filename, jd_file)

            resp = requests.post(
                f"{self.base_url}/api/v1/chat",
                data=data,
                files=files if files else None,
                timeout=180,  # Agent 可能串行调用多个 LLM，给更长时间
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}


# 全局单例
api = APIClient()
