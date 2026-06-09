"""页面 3 - 简历优化。

基于目标岗位生成优化建议。
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="✨ 简历优化", page_icon="✨", layout="wide")

st.header("✨ 简历优化")
st.caption("提供简历与目标岗位，自动生成优化建议与段落改写")

tab1, tab2 = st.tabs(["📝 生成优化建议", "✏️ 段落重写"])

with tab1:
    resume_id = st.text_input("简历 ID")
    target_jd = st.text_area(
        "目标岗位描述（可选）",
        height=200,
        placeholder="请粘贴目标岗位 JD...",
    )
    if st.button("🚀 生成建议", type="primary"):
        st.info("🔧 优化建议功能在阶段 4（Optimizer Agent）实现。")

with tab2:
    target_role = st.text_input("目标岗位（用于指导改写方向）")
    paragraph = st.text_area("原始段落", height=200, placeholder="粘贴你想优化的段落...")
    if st.button("✍️ 重写", type="primary"):
        st.info("🔧 段落重写功能在阶段 4（Optimizer Agent）实现。")
