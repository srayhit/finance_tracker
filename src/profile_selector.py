import streamlit as st
from src.config import USERS

def render_profile_selector():
    """Renders the user profile identification dropdown in the sidebar."""
    st.sidebar.title("👤 User Profile")
    
    if "current_user" not in st.session_state:
        st.session_state["current_user"] = USERS[0]
        
    selected_user = st.sidebar.selectbox(
        "Who is viewing?", 
        options=USERS, 
        index=USERS.index(st.session_state["current_user"])
    )
    st.session_state["current_user"] = selected_user
    st.sidebar.caption(f"Logged in implicitly as: **{selected_user}**")
