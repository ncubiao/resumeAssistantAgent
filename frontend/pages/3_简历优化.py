"""页面 3 - 简历优化。"""
from __future__ import annotations

import streamlit as st

from components.api_client import api
from components.resume_selector import resume_selector

st.set_page_config(page_title="简历优化", page_icon="📋", layout="wide")

st.title("简历优化")
st.caption("生成针对性优化建议，或对单个段落润色重写")

tab1, tab2 = st.tabs(["生成优化建议", "段落重写"])

with tab1:
    st.subheader("简历")
    resume_id = resume_selector("optimize")
    target_jd = st.text_area(
        "目标岗位描述（可选，提供后建议更有针对性）",
        height=160,
        placeholder="粘贴目标岗位 JD...",
    )

    if st.button("生成建议", type="primary", disabled=not resume_id, use_container_width=True):
        with st.spinner("生成中..."):
            result = api.optimize_suggestions(resume_id, target_jd or None)

        if isinstance(result, dict) and "error" in result:
            st.error(f"生成失败：{result['error']}")
        elif result:
            suggestions = result.get("suggestions") or []
            if not suggestions:
                st.caption("未生成建议")
            for i, sug in enumerate(suggestions, 1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {sug.get('category', '其他')}**")
                    if sug.get("original"):
                        st.caption(f"原文：{sug['original']}")
                    st.write(sug.get("improved", ""))
                    st.caption(sug.get("reason", ""))

with tab2:
    target_role = st.text_input("目标岗位（可选，用于指导改写方向）")
    paragraph = st.text_area(
        "原始段落", height=180, placeholder="粘贴想优化的段落..."
    )

    if st.button(
        "重写", type="primary", disabled=not (paragraph and paragraph.strip()), use_container_width=True
    ):
        with st.spinner("重写中..."):
            result = api.optimize_rewrite(paragraph, target_role or None)

        if isinstance(result, dict) and "error" in result:
            st.error(f"重写失败：{result['error']}")
        elif result:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("原文")
                st.write(result.get("original", ""))
            with c2:
                st.subheader("重写后")
                st.write(result.get("rewritten", ""))
            highlights = result.get("highlights") or []
            if highlights:
                st.caption("改写要点")
                for h in highlights:
                    st.markdown(f"- {h}")
