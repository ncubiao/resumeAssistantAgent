"""智能助手 —— 多轮对话 Agent，含会话持久化与长期记忆。"""
from __future__ import annotations

import json
import os
import uuid as _uuid

import streamlit as st

from components.api_client import api

st.set_page_config(page_title="智能助手", page_icon="📋", layout="wide")

# -------- 会话/用户状态（user_id 本期默认匿名，预留登录） --------
if "user_id" not in st.session_state:
    st.session_state.user_id = "u-" + _uuid.uuid4().hex[:8]
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_role" not in st.session_state:
    st.session_state.user_role = "recruiter"
if "backend_url" not in st.session_state:
    st.session_state.backend_url = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
api.base_url = st.session_state.backend_url.rstrip("/")


def _load_conversation(conv_id: str) -> None:
    detail = api.get_conversation(conv_id)
    if not detail or (isinstance(detail, dict) and detail.get("error")):
        st.error("加载会话失败")
        return
    st.session_state.session_id = detail["id"]
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"], "tool_calls": m.get("tool_calls", [])}
        for m in detail.get("messages", [])
    ]


# ============== 侧栏 ==============
with st.sidebar:
    if st.button("新会话", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

    st.subheader("历史会话")
    convs = api.list_conversations(st.session_state.user_id)
    if convs:
        for c in convs[:20]:
            label = (c.get("title") or "未命名")[:22]
            is_current = c["id"] == st.session_state.session_id
            prefix = "● " if is_current else "  "
            if st.button(
                f"{prefix}{label}",
                key=f"conv_{c['id']}",
                use_container_width=True,
                type="secondary",
            ):
                _load_conversation(c["id"])
                st.rerun()
    else:
        st.caption("暂无历史")

    memories = api.get_memories(st.session_state.user_id)
    if memories:
        with st.expander(f"长期记忆（{len(memories)}）", expanded=False):
            for m in memories[:15]:
                st.caption(f"· {m.get('content', '')}")

    with st.expander("高级设置", expanded=False):
        new_url = st.text_input(
            "后端 API",
            value=st.session_state.backend_url,
            label_visibility="collapsed",
        )
        if new_url != st.session_state.backend_url:
            st.session_state.backend_url = new_url
            api.base_url = new_url.rstrip("/")
        if st.button("测试连接", use_container_width=True):
            ok, info = api.health_check()
            (st.success if ok else st.error)(f"{info}")
        st.caption(f"用户 ID: {st.session_state.user_id}")


# ============== 主区域 ==============
st.title("智能助手")

# 身份切换 + 文件上传 紧凑放一行
top_l, top_r = st.columns([1, 2])
with top_l:
    role_label = st.radio(
        "身份",
        ["招聘方", "求职者"],
        index=0 if st.session_state.user_role == "recruiter" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state.user_role = "recruiter" if role_label == "招聘方" else "candidate"

with top_r:
    if st.session_state.user_role == "recruiter":
        chat_placeholder = "例如：帮我评估这位候选人是否适合 Python 后端"
    else:
        chat_placeholder = "例如：帮我看看我的简历适合什么岗位"
    st.caption(chat_placeholder)

with st.expander("附加文件（可选）", expanded=False):
    fc1, fc2 = st.columns(2)
    with fc1:
        resume_uploaded = st.file_uploader(
            "简历",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
            key="resume_upload",
        )
    with fc2:
        jd_uploaded = st.file_uploader(
            "岗位描述 (JD)",
            type=["pdf", "docx", "doc", "txt", "md", "png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
            key="jd_upload",
        )

st.divider()

# -------- 渲染历史消息 --------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for tc in msg.get("tool_calls", []):
            with st.expander(f"调用工具 · {tc.get('tool_name')}", expanded=False):
                try:
                    parsed = json.loads(tc.get("tool_input", "{}"))
                    for k, v in parsed.items():
                        val = str(v)
                        if len(val) > 300:
                            val = val[:300] + "..."
                        st.write(f"- `{k}`: {val}")
                except Exception:
                    st.code(tc.get("tool_input", ""))
                out = tc.get("tool_output") or tc.get("truncated_output") or ""
                if out:
                    st.code(out[:2000], language="json")


# -------- 用户输入 --------
if user_input := st.chat_input("发送消息..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    resume_bytes = resume_uploaded.read() if resume_uploaded else None
    resume_name = resume_uploaded.name if resume_uploaded else None
    jd_bytes = jd_uploaded.read() if jd_uploaded else None
    jd_name = jd_uploaded.name if jd_uploaded else None

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[-10:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            result = api.chat(
                message=user_input,
                resume_file=resume_bytes,
                resume_filename=resume_name,
                jd_file=jd_bytes,
                jd_filename=jd_name,
                history=history,
                user_role=st.session_state.user_role,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        if result is None or (isinstance(result, dict) and result.get("error")):
            msg = (
                result.get("error", "调用失败")
                if isinstance(result, dict)
                else "调用失败"
            )
            st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
        else:
            if result.get("session_id"):
                st.session_state.session_id = result["session_id"]

            answer = result.get("answer", "") or "(空回答)"
            tool_calls = result.get("tool_calls", []) or []
            recalled = result.get("recalled_memories") or []

            st.markdown(answer)

            if recalled:
                with st.expander(f"召回了 {len(recalled)} 条长期记忆", expanded=False):
                    for m in recalled:
                        st.caption(f"· {m}")

            for tc in tool_calls:
                with st.expander(f"调用工具 · {tc.get('tool_name')}", expanded=False):
                    try:
                        parsed = json.loads(tc.get("tool_input", "{}"))
                        for k, v in parsed.items():
                            val = str(v)
                            if len(val) > 300:
                                val = val[:300] + "..."
                            st.write(f"- `{k}`: {val}")
                    except Exception:
                        st.code(tc.get("tool_input", ""))
                    out = tc.get("tool_output") or tc.get("truncated_output") or ""
                    if out:
                        st.code(out[:2000], language="json")

            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "tool_calls": tool_calls}
            )
