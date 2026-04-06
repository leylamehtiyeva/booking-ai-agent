import html
import json

import streamlit as st

from ui.state import get_messages


def render_messages() -> None:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    for idx, message in enumerate(get_messages()):
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

            debug_data = message.get("debug_data")
            if debug_data:
                with st.expander("Debug: parsed intent / search request", expanded=False):
                    parsed_intent = debug_data.get("parsed_intent")
                    search_request = debug_data.get("search_request")
                    state_after = debug_data.get("state_after")

                    if parsed_intent is not None:
                        st.markdown("**Parsed intent**")
                        st.code(
                            json.dumps(parsed_intent, ensure_ascii=False, indent=2, default=str),
                            language="json",
                        )

                    if search_request is not None:
                        st.markdown("**Search request**")
                        st.code(
                            json.dumps(search_request, ensure_ascii=False, indent=2, default=str),
                            language="json",
                        )

                    if state_after is not None:
                        st.markdown("**Current state after turn**")
                        st.code(
                            json.dumps(state_after, ensure_ascii=False, indent=2, default=str),
                            language="json",
                        )

    st.markdown("</div>", unsafe_allow_html=True)