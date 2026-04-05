import streamlit as st


def render_header() -> None:
    st.markdown(
        """
        <div class="app-header">
            <div class="brand">AI Booking System</div>
        </div>
        """,
        unsafe_allow_html=True,
    )