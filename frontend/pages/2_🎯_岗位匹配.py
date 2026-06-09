"""页面 2 - 岗位匹配。

输入 JD 和简历，计算匹配度。
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="🎯 岗位匹配", page_icon="🎯", layout="wide")

st.header("🎯 岗位匹配")
st.caption("输入岗位描述（JD）与简历 ID，计算匹配度")

col1, col2 = st.columns([1, 2])
with col1:
    resume_id = st.text_input("简历 ID", value="（请先在「简历解析」页上传并获取 ID）")
    st.markdown("**或**")
    uploaded = st.file_uploader("上传一份简历", type=["pdf", "docx", "doc", "txt"])

with col2:
    jd = st.text_area(
        "岗位描述 (JD)",
        height=300,
        placeholder="例如：3 年以上 Python 后端开发经验，熟悉 FastAPI / PostgreSQL...",
    )

if st.button("🚀 开始匹配", type="primary", disabled=not jd):
    st.info("🔧 匹配功能在阶段 4（Matcher Agent）实现。当前为骨架占位页面。")
    st.write("预期输出：")
    st.json({
        "overall_score": 0.0,
        "breakdown": {"skill_match": 0.0, "experience_match": 0.0, "education_match": 0.0},
        "strengths": [],
        "gaps": [],
    })
