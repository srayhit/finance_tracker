import streamlit as st
from src.config import USERS


def render_profile_selector():
    """Renders the user profile selector and returns the active user and view mode."""
    st.sidebar.title("👤 User Profile")

    if "current_user" not in st.session_state:
        st.session_state["current_user"] = USERS[0]
    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "Individual"

    selected_user = st.sidebar.selectbox(
        "Who is viewing?",
        options=USERS,
        index=USERS.index(st.session_state["current_user"]),
    )
    view_mode = st.sidebar.radio(
        "View Mode",
        ["Individual", "Combined"],
        index=0 if st.session_state["view_mode"] == "Individual" else 1,
        horizontal=True,
    )

    st.session_state["current_user"] = selected_user
    st.session_state["view_mode"] = view_mode
    st.sidebar.caption(f"Logged in implicitly as: **{selected_user}**")
    return selected_user, view_mode
