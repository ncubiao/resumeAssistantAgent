"""智能助手聊天页：用户上传文件 + 多轮对话，Agent 自动调用工具。"""
from __future__ import annotations

import json
import os

import streamlit as st

from components.api_client import api

st.set_page_config(page_title="智能助手 | 简历小助手", page_icon="💬", layout="wide")

# 后端地址
default_url = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
with st.sidebar:
    st.subheader("⚙️ 后端配置")
    backend_url = st.text_input("Backend API URL", value=default_url)
    api.base_url = backend_url.rstrip("/")

    if st.button("🔌 检查后端连接", use_container_width=True):
        with st.spinner("Ping 中..."):
            ok, info = api.health_check()
            if ok:
                st.success(f"✅ 后端可用: {info}")
            else:
                st.error(f"❌ 后端不可用: {info}")

    st.divider()
    st.caption("💡 使用提示")
    st.caption("1. 先上传简历/JD，或直接提问")
    st.caption("2. 支持多轮对话，上下文自动保持")
    st.caption("3. 可在思考过程中看到 Agent 调用了哪些工具")


st.title("💬 简历智能助手")
st.caption("上传简历或岗位描述，用自然语言和 AI 对话：解析、匹配、优化，一次搞定。")

# -------- 上传区 --------
with st.expander("📎 上传文件（可选）", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        resume_uploaded = st.file_uploader(
            "上传简历（PDF / Word / TXT / MD / 图片 PNG JPG WEBP）",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
            accept_multiple_files=False,
            key="resume_upload",
        )
    with col2:
        jd_uploaded = st.file_uploader(
            "上传岗位描述 JD（PDF / Word / TXT / MD / 图片 PNG JPG WEBP）",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
            accept_multiple_files=False,
            key="jd_upload",
        )

    if resume_uploaded is not None:
        st.success(f"✅ 已准备简历: {resume_uploaded.name}")
    if jd_uploaded is not None:
        st.success(f"✅ 已准备 JD: {jd_uploaded.name}")


# -------- 聊天消息状态 --------
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.button("🧹 清空对话", type="secondary"):
    st.session_state.messages = []
    st.rerun()

# 渲染已有消息
for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])
        # 若是 assistant 且带有 tool_calls，再把工具过程折叠展示
        for tc in msg.get("tool_calls", []):
            with st.expander(f"🛠️ 调用了工具：{tc.get('tool_name')}"):
                st.markdown("**输入参数：**")
                try:
                    parsed = json.loads(tc.get("tool_input", "{}"))
                    # 长文本截断显示
                    for k, v in parsed.items():
                        val = str(v)
                        if len(val) > 300:
                            val = val[:300] + "..."
                        st.write(f"- `{k}`: {val}")
                except Exception:
                    st.code(tc.get("tool_input", ""))
                st.markdown("**返回结果（节选）：**")
                out = tc.get("tool_output") or tc.get("truncated_output") or ""
                st.code(out[:2000], language="json")

# 用户输入
if user_input := st.chat_input("输入消息，比如：『帮我看看这份简历适合什么岗位』"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 准备发送给后端
    resume_bytes = None
    resume_name = None
    if resume_uploaded is not None:
        resume_bytes = resume_uploaded.read()
        resume_name = resume_uploaded.name

    jd_bytes = None
    jd_name = None
    if jd_uploaded is not None:
        jd_bytes = jd_uploaded.read()
        jd_name = jd_uploaded.name

    # 只保留最近 10 条历史，避免 prompt 过长
    history = [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("Agent 正在思考并调用工具..."):
            result = api.chat(
                message=user_input,
                resume_file=resume_bytes,
                resume_filename=resume_name,
                jd_file=jd_bytes,
                jd_filename=jd_name,
                history=history,
            )

        if result is None or isinstance(result, dict) and result.get("error"):
            msg = result.get("error", "调用失败，请检查后端是否启动。") if isinstance(result, dict) else "调用失败"
            st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {msg}"})
        else:
            answer = result.get("answer", "") or "(空回答)"
            tool_calls = result.get("tool_calls", []) or []
            used_tools = result.get("used_tools", False)

            st.markdown(answer)

            if used_tools and tool_calls:
                for tc in tool_calls:
                    with st.expander(f"🛠️ 调用了工具：{tc.get('tool_name')}"):
                        st.markdown("**输入参数：**")
                        try:
                            parsed = json.loads(tc.get("tool_input", "{}"))
                            for k, v in parsed.items():
                                val = str(v)
                                if len(val) > 300:
                                    val = val[:300] + "..."
                                st.write(f"- `{k}`: {val}")
                        except Exception:
                            st.code(tc.get("tool_input", ""))
                        st.markdown("**返回结果（节选）：**")
                        out = tc.get("tool_output") or tc.get("truncated_output") or ""
                        st.code(out[:2000], language="json")

            # 写入会话状态
            assistant_msg = {"role": "assistant", "content": answer, "tool_calls": tool_calls}
            st.session_state.messages.append(assistant_msg)
