"""页面 1 - 简历解析。"""
from __future__ import annotations

import streamlit as st

from components.api_client import api

st.set_page_config(page_title="简历解析", page_icon="📋", layout="wide")

st.title("简历解析")
st.caption("上传简历文件，自动提取结构化信息")

uploaded = st.file_uploader(
    "选择简历文件",
    type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
    accept_multiple_files=False,
    label_visibility="collapsed",
)

if uploaded is None:
    st.stop()

with st.spinner("解析中..."):
    raw = uploaded.read()
    result = api.upload_resume(raw, uploaded.name)

if isinstance(result, dict) and "error" in result:
    st.error(f"解析失败：{result['error']}")
    st.stop()

if not result:
    st.warning("后端返回空结果")
    st.stop()


# -------- 顶部：简历 ID（便于跨页复用） --------
rid = str(result.get("id") or "")
if rid:
    st.code(rid, language=None)
    st.caption("简历 ID（可在岗位匹配 / 简历优化 / Agent 编排页选用）")

st.divider()

# -------- 主区域：左基本信息，右原文预览 --------
col1, col2 = st.columns([1, 2])

with col1:
    fields = [
        ("姓名", result.get("name")),
        ("邮箱", result.get("email")),
        ("电话", result.get("phone")),
        ("学历", result.get("education_level")),
        ("工作年限", result.get("years_of_experience")),
    ]
    for label, value in fields:
        st.text_input(label, value=str(value or ""), disabled=True)

    skills = result.get("skills") or []
    if skills:
        st.caption("技能")
        st.write("　".join(skills))

with col2:
    st.text_area(
        "原始文本",
        value=result.get("raw_text", ""),
        height=440,
        label_visibility="collapsed",
        disabled=True,
    )

# -------- 折叠：完整 JSON --------
with st.expander("完整解析结果（JSON）", expanded=False):
    st.json(result)
