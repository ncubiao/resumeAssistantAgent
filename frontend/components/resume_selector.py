"""共享 UI 组件：简历选择器。

简约风：纯文字、不啰嗦提示。返回一个已落库的 resume_id。
"""
from __future__ import annotations

import streamlit as st

from components.api_client import api


def _label_for(resume: dict) -> str:
    name = resume.get("name") or "(未命名)"
    filename = resume.get("filename") or ""
    rid = str(resume.get("id") or "")[:8]
    return f"{name} · {filename} · {rid}" if filename else f"{name} · {rid}"


def resume_selector(key_prefix: str) -> str | None:
    """返回一个已落库的 resume_id（或 None）。"""
    source = st.radio(
        "来源",
        ["选择已有", "上传文件", "粘贴文本"],
        horizontal=True,
        key=f"{key_prefix}_source",
        label_visibility="collapsed",
    )

    if source == "选择已有":
        resumes = api.list_resumes()
        if not resumes:
            st.caption("尚无已解析的简历，请切换到上传或粘贴。")
            return None
        options = {_label_for(r): str(r.get("id")) for r in resumes}
        chosen = st.selectbox(
            "简历", list(options.keys()), key=f"{key_prefix}_select", label_visibility="collapsed"
        )
        return options.get(chosen)

    if source == "上传文件":
        uploaded = st.file_uploader(
            "上传简历",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp"],
            key=f"{key_prefix}_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            with st.spinner("解析中..."):
                result = api.upload_resume(uploaded.read(), uploaded.name)
            if isinstance(result, dict) and "error" in result:
                st.error(f"上传失败：{result['error']}")
                return None
            if result and result.get("id"):
                st.caption(f"已入库：{result.get('name') or uploaded.name}")
                return str(result["id"])
        return None

    # 粘贴文本
    text = st.text_area(
        "粘贴简历文本",
        height=180,
        key=f"{key_prefix}_text",
        label_visibility="collapsed",
        placeholder="将简历文本粘贴到这里...",
    )
    if text and text.strip():
        if st.button("提交", key=f"{key_prefix}_text_submit"):
            with st.spinner("解析中..."):
                result = api.parse_text(text)
            if isinstance(result, dict) and "error" in result:
                st.error(f"提交失败：{result['error']}")
                return None
            if result and result.get("id"):
                st.session_state[f"{key_prefix}_text_rid"] = str(result["id"])
                st.caption("已入库")
    return st.session_state.get(f"{key_prefix}_text_rid")
