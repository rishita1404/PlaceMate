"""
app/ui/pages/dashboard.py
────────────────────────
Dashboard overview: metrics, profile status, and quick job discoveries.
"""

import streamlit as st
from app.ui import api_client


def render():
    user = st.session_state.get("user") or {}
    email = user.get("email", "Student")

    st.title("🎯 PlaceMate AI Dashboard")
    st.markdown(f"Welcome back, **{email}**! Here is an overview of your career discovery progress.")

    # ── Fetch Profile & Jobs & Applications Data ──
    profile_data = {}
    is_confirmed = False
    profile_res = api_client.get_profile()
    if profile_res["ok"]:
        profile_data = profile_res["data"]
        is_confirmed = profile_data.get("is_confirmed", False)

    jobs_res = api_client.list_jobs(limit=100)
    jobs_list = jobs_res["data"] if jobs_res["ok"] and isinstance(jobs_res["data"], list) else []

    apps_res = api_client.list_applications()
    apps_list = apps_res["data"] if apps_res["ok"] and isinstance(apps_res["data"], list) else []

    # ── Status Banners ──
    st.write("")
    if not is_confirmed:
        st.warning(
            "⚠️ **Your profile is not yet confirmed!**\n\n"
            "Job matching and AI features require a confirmed profile with your verified skills and education. "
            "Please visit your profile to review and confirm."
        )
        if st.button("👉 Complete & Confirm Profile", key="dash_goto_profile"):
            st.session_state.page = "profile"
            st.rerun()
    else:
        st.success(
            f"✅ **Profile Confirmed**: {profile_data.get('degree', '') or 'Student'} • "
            f"{len(profile_data.get('skills', []))} skills on file. Tailored matching is active!"
        )

    st.write("")

    # ── Key Metrics ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Active Jobs", value=len(jobs_list))
    with col2:
        st.metric(label="My Applications", value=len(apps_list))
    with col3:
        skills_count = len(profile_data.get("skills", []))
        st.metric(label="Recorded Skills", value=skills_count)
    with col4:
        gpa = profile_data.get("gpa")
        st.metric(label="Recorded GPA", value=f"{gpa}" if gpa is not None else "Not set")

    st.divider()

    # ── Quick Action Cards ──
    st.subheader("⚡ Quick Actions")
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)
    with qcol1:
        if st.button("💼 Browse All Jobs", use_container_width=True):
            st.session_state.page = "jobs"
            st.rerun()
    with qcol2:
        if st.button("📄 Upload / Parse Resume", use_container_width=True):
            st.session_state.page = "resume"
            st.rerun()
    with qcol3:
        if st.button("📊 Application Tracker", use_container_width=True):
            st.session_state.page = "tracker"
            st.rerun()
    with qcol4:
        if st.button("👤 Edit Profile", use_container_width=True):
            st.session_state.page = "profile"
            st.rerun()

    st.divider()

    # ── Featured Openings ──
    st.subheader("🌟 Featured Opportunities")
    if not jobs_list:
        st.info("No active job postings found. Check back later or import jobs in the Admin panel.")
    else:
        for job in jobs_list[:5]:
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{job.get('title')}**")
                    company = job.get("company_name") or "Direct Hire"
                    st.caption(f"🏢 {company} • 📍 {job.get('location', 'Remote/Flexible')}")
                with c2:
                    jtype = (job.get("job_type") or "").replace("_", " ").title()
                    deadline = (job.get("deadline") or "")[:10] if job.get("deadline") else "Open"
                    st.markdown(f"Type: **{jtype}** | Deadline: `{deadline}`")
                with c3:
                    if st.button("View Job", key=f"dash_view_job_{job.get('id')}", use_container_width=True):
                        st.session_state.selected_job_id = job.get("id")
                        st.session_state.page = "jobs"
                        st.rerun()
                st.write("---")
