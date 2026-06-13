"""后端 API 客户端封装。"""
from __future__ import annotations

import os
from typing import Any

import requests


class APIClient:
    """统一 API 客户端，供所有 Streamlit 页面共用。"""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = 30
        # 可选 API Key：后端开启鉴权时通过环境变量提供，默认无（与后端默认关闭对应）
        self.api_key = os.environ.get("BACKEND_API_KEY", "")
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"X-API-Key": self.api_key})

    # ---------- 通用 ----------

    def health_check(self) -> tuple[bool, str]:
        try:
            resp = self._session.get(f"{self.base_url}/health", timeout=self.timeout)
            resp.raise_for_status()
            return True, resp.json().get("service", "ok")
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    # ---------- 简历 ----------

    def upload_resume(self, file_bytes: bytes, filename: str) -> dict[str, Any] | None:
        try:
            files = {"file": (filename, file_bytes)}
            resp = self._session.post(
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
            resp = self._session.get(f"{self.base_url}/api/v1/resumes", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json() or []
        except Exception:  # noqa: BLE001
            return []

    def get_resume(self, resume_id: str) -> dict[str, Any] | None:
        try:
            resp = self._session.get(
                f"{self.base_url}/api/v1/resumes/{resume_id}", timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def parse_text(self, text: str) -> dict[str, Any] | None:
        """直接提交简历文本，落库并返回（含 id）。"""
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/resumes/parse-text",
                json={"text": text},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def search_resumes(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/resumes/search",
                json={"query": query, "k": k},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json() or []
        except Exception:  # noqa: BLE001
            return []

    # ---------- 匹配 ----------

    def match_single(self, resume_id: str, jd: str) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/matches/single",
                json={"resume_id": resume_id, "jd": jd},
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def match_batch(self, resume_ids: list[str], jd: str) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/matches/batch",
                json={"resume_ids": resume_ids, "jd": jd},
                timeout=300,  # 多份简历串行调 LLM
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # ---------- 优化 ----------

    def optimize_suggestions(self, resume_id: str, target_jd: str | None = None) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/optimize/suggestions",
                json={"resume_id": resume_id, "target_jd": target_jd},
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def optimize_rewrite(self, paragraph: str, target_role: str | None = None) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/optimize/rewrite",
                json={"paragraph": paragraph, "target_role": target_role},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # ---------- Agent 编排 ----------

    def agent_analyze(
        self,
        resume_id: str | None = None,
        raw_text: str | None = None,
        jd: str | None = None,
        mode: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any] | None:
        try:
            body: dict[str, Any] = {}
            if resume_id:
                body["resume_id"] = resume_id
            if raw_text:
                body["raw_text"] = raw_text
            if jd:
                body["jd"] = jd
            if mode:
                body["mode"] = mode
            if thread_id:
                body["thread_id"] = thread_id
            resp = self._session.post(
                f"{self.base_url}/api/v1/agent/analyze",
                json=body,
                timeout=300,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # ---------- 聊天 Agent ----------

    def chat(
        self,
        message: str,
        resume_file: bytes | None = None,
        resume_filename: str | None = None,
        jd_file: bytes | None = None,
        jd_filename: str | None = None,
        history: list[dict[str, str]] | None = None,
        user_role: str = "recruiter",
    ) -> dict[str, Any] | None:
        try:
            data = {"message": message, "user_role": user_role}
            if history:
                import json as _json

                data["history"] = _json.dumps(history)
            files: dict[str, tuple[str, bytes]] = {}
            if resume_file is not None and resume_filename:
                files["resume_file"] = (resume_filename, resume_file)
            if jd_file is not None and jd_filename:
                files["jd_file"] = (jd_filename, jd_file)

            resp = self._session.post(
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
