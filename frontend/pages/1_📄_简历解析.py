"""页面 1 - 简历解析。

上传简历文件并展示解析后的结构化信息。
"""
from __future__ import annotations

import streamlit as st

from components.api_client import api

st.set_page_config(page_title="📄 简历解析", page_icon="📄", layout="wide")

st.header("📄 简历解析")
st.caption("上传 PDF / Word / 图片 简历，自动提取结构化信息")

uploaded = st.file_uploader(
    "选择简历文件",
    type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
    accept_multiple_files=False,
)

if uploaded is not None:
    with st.spinner("正在解析..."):
        raw = uploaded.read()
        result = api.upload_resume(raw, uploaded.name)

    if isinstance(result, dict) and "error" in result:
        st.error(f"❌ 解析失败: {result['error']}")
    elif result:
        st.success("✅ 解析完成")

        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📋 基本信息")
            st.write(f"**文件名**: {result.get('filename')}")
            st.write(f"**姓名**: {result.get('name') or '—'}")
            st.write(f"**邮箱**: {result.get('email') or '—'}")
            st.write(f"**电话**: {result.get('phone') or '—'}")
            st.write(f"**学历**: {result.get('education_level') or '—'}")
            st.write(f"**工作年限**: {result.get('years_of_experience') or '—'}")
            st.write(f"**置信度**: {result.get('parse_confidence'):.2f}")

            skills = result.get("skills") or []
            st.subheader("🏷️ 技能")
            if skills:
                st.write("、".join(skills))
            else:
                st.caption("（当前为骨架版本，技能提取在阶段 3 接入）")

        with col2:
            st.subheader("📝 原始文本（截断预览）")
            st.text_area(
                "raw_text",
                value=result.get("raw_text", ""),
                height=400,
                label_visibility="collapsed",
            )

            with st.expander("🔍 完整 JSON"):
                st.json(result)
    else:
        st.info("后端返回空结果，请检查后端状态。")
