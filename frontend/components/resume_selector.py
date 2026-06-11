"""共享 UI 组件：简历选择器。

让页面 2/3/4 复用同一套"选已有简历 / 内联上传 / 粘贴文本"的交互，
统一返回一个 resume_id（已落库）。
"""
from __future__ import annotations

import streamlit as st

from components.api_client import api


def _label_for(resume: dict) -> str:
    name = resume.get("name") or "(未命名)"
    filename = resume.get("filename") or ""
    rid = str(resume.get("id") or "")
    short = rid[:8]
    skills = resume.get("skills") or []
    skill_hint = f" · {len(skills)} 技能" if skills else ""
    return f"{name} · {filename}{skill_hint} · {short}"


def resume_selector(key_prefix: str) -> str | None:
    """渲染简历来源选择器，返回一个已落库的 resume_id（或 None）。

    三种来源：
    1. 从已有简历下拉选择
    2. 上传新文件（自动落库）
    3. 粘贴纯文本（自动落库）
    """
    source = st.radio(
        "简历来源",
        ["选择已有简历", "上传新文件", "粘贴文本"],
        horizontal=True,
        key=f"{key_prefix}_source",
    )

    if source == "选择已有简历":
        resumes = api.list_resumes()
        if not resumes:
            st.warning("还没有任何简历，请先在「简历解析」页上传，或切换到上传/粘贴。")
            return None
        options = {_label_for(r): str(r.get("id")) for r in resumes}
        chosen = st.selectbox("选择简历", list(options.keys()), key=f"{key_prefix}_select")
        return options.get(chosen)

    if source == "上传新文件":
        uploaded = st.file_uploader(
            "上传简历",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp"],
            key=f"{key_prefix}_upload",
        )
        if uploaded is not None:
            with st.spinner("正在解析并入库..."):
                result = api.upload_resume(uploaded.read(), uploaded.name)
            if isinstance(result, dict) and "error" in result:
                st.error(f"上传失败：{result['error']}")
                return None
            if result and result.get("id"):
                st.success(f"已入库：{result.get('name') or uploaded.name}（{str(result['id'])[:8]}）")
                return str(result["id"])
        return None

    # 粘贴文本
    text = st.text_area("粘贴简历文本", height=200, key=f"{key_prefix}_text")
    if text and text.strip():
        if st.button("提交文本并入库", key=f"{key_prefix}_text_submit"):
            with st.spinner("正在解析并入库..."):
                result = api.parse_text(text)
            if isinstance(result, dict) and "error" in result:
                st.error(f"提交失败：{result['error']}")
                return None
            if result and result.get("id"):
                # 存进 session_state 以便按钮点击后保留
                st.session_state[f"{key_prefix}_text_rid"] = str(result["id"])
                st.success(f"已入库：{str(result['id'])[:8]}")
    return st.session_state.get(f"{key_prefix}_text_rid")
