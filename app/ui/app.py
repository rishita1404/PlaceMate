"""
app/ui/app.py
─────────────
PlaceMate AI — Streamlit frontend entry point.

Run with:
    .venv/bin/streamlit run app/ui/app.py --server.port 8501

Architecture:
  - All API calls go through app/ui/api_client.py
  - Each page is a function in its own module under app/ui/pages/
  - Session state keys:
      st.session_state.token       — JWT Bearer token (str | None)
      st.session_state.user        — user dict from /auth/register or /auth/login
      st.session_state.page        — active page name
"""

import sys
from pathlib import Path

# Ensure project root is always on sys.path regardless of execution cwd
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="PlaceMate AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialise session state ──────────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

# ── Import view renderers ─────────────────────────────────────────────────────
from app.ui.views import (
    auth as auth_page,
    dashboard as dashboard_page,
    profile as profile_page,
    jobs as jobs_page,
    tracker as tracker_page,
    resume as resume_page,
    admin as admin_page,
)

# ── Sidebar navigation ────────────────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("## 🎯 PlaceMate AI")
        st.markdown("*Career discovery for students*")
        st.divider()

        if st.session_state.token:
            user = st.session_state.user or {}
            st.markdown(f"👤 **{user.get('email', 'Student')}**")
            role = user.get("role", "student")
            if role == "admin":
                st.caption("🔑 Admin")
            st.divider()

            pages = {
                "🏠 Dashboard": "dashboard",
                "👤 My Profile": "profile",
                "📄 Upload Resume": "resume",
                "💼 Browse Jobs": "jobs",
                "📊 Application Tracker": "tracker",
            }
            if role == "admin":
                pages["⚙️ Admin"] = "admin"

            for label, page_key in pages.items():
                if st.button(label, key=f"nav_{page_key}", use_container_width=True):
                    st.session_state.page = page_key

            st.divider()
            if st.button("🚪 Sign Out", use_container_width=True):
                st.session_state.token = None
                st.session_state.user = None
                st.session_state.page = "dashboard"
                st.rerun()
        else:
            if st.button("🔑 Sign In / Register", use_container_width=True):
                st.session_state.page = "auth"

        st.divider()
        st.caption("PlaceMate AI v0.1.0-mvp")
        st.caption("Backend: http://127.0.0.1:8002")


# ── Main router ───────────────────────────────────────────────────────────────
def main():
    sidebar()

    page = st.session_state.page

    # Redirect unauthenticated users away from protected pages
    protected = {"profile", "resume", "jobs", "tracker", "admin"}
    if page in protected and not st.session_state.token:
        st.warning("⚠️ Please sign in to access this page.")
        auth_page.render()
        return

    if page == "auth":
        auth_page.render()
    elif page == "dashboard":
        dashboard_page.render()
    elif page == "profile":
        profile_page.render()
    elif page == "resume":
        resume_page.render()
    elif page == "jobs":
        jobs_page.render()
    elif page == "tracker":
        tracker_page.render()
    elif page == "admin":
        admin_page.render()
    else:
        dashboard_page.render()


if __name__ == "__main__":
    main()
