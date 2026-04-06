import streamlit as st


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "search_state" not in st.session_state:
        st.session_state.search_state = None


def get_messages():
    return st.session_state.messages


def get_search_state():
    return st.session_state.search_state


def set_search_state(state) -> None:
    st.session_state.search_state = state


def append_message(role: str, content: str, debug_data=None) -> None:
    message = {
        "role": role,
        "content": content,
    }
    if debug_data is not None:
        message["debug_data"] = debug_data

    st.session_state.messages.append(message)