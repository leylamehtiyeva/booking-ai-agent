import html

import streamlit as st

from ui.state import get_messages


def render_messages() -> None:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    for message in get_messages():
        role = message["role"]
        raw_content = message["content"]
        safe_content = html.escape(raw_content).replace("\n", "<br>")

        if role == "user":
            st.markdown(
                f"""
                <div class="message-row user-row">
                    <div class="chat-bubble user-bubble">{safe_content}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="message-row assistant-row">
                    <div class="chat-bubble assistant-bubble">{safe_content}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)