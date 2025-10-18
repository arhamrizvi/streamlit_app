import streamlit as st
from supabase import create_client

@st.cache_resource(show_spinner=False)
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)
