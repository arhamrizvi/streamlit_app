import streamlit as st
from .supabase_client import get_supabase

def ensure_session():
    if "session" not in st.session_state:
        st.session_state.session = None

def sign_in(email: str, password: str):
    supabase = get_supabase()
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    # res has .user and .session
    st.session_state.session = res.session
    return res

def sign_out():
    supabase = get_supabase()
    supabase.auth.sign_out()
    st.session_state.session = None

def require_auth():
    ensure_session()
    if st.session_state.session is None:
        with st.sidebar:
            st.header("Sign in")
            email = st.text_input("Email", key="login_email")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Sign in"):
                try:
                    res = sign_in(email, pwd)
                    if res.user:
                        st.success("Signed in.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
        st.stop()

def current_user_email() -> str | None:
    if st.session_state.get("session") and st.session_state.session.user:
        return st.session_state.session.user.email
    return None
