import streamlit as st


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-state">
            <div>
                <div class="empty-title">Find stays with natural language</div>
                <div class="empty-subtitle">
                    Tell me where you want to stay, when, and what matters to you —
                    and I’ll help you find matching places.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )