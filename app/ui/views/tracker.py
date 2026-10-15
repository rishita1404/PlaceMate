"""
app/ui/pages/tracker.py
──────────────────────
Application Tracker view: manage ongoing applications, transitions, and confirmation receipts.
"""

import streamlit as st
from app.ui import api_client


STATUS_OPTIONS = [
    "draft",
    "applied",
    "submitted_confirmed",
    "under_review",
    "interview_scheduled",
    "offer",
    "rejected",
    "withdrawn",
]


def render():
    st.title("📊 Application Tracker")
    st.markdown("Track and manage the progress of your internship and placement applications.")

    res = api_client.list_applications()
    if not res["ok"]:
        st.error(f"Failed to load applications: {res['data'].get('detail', 'Unknown error')}")
        return

    applications = res["data"]
    if not applications:
        st.info("You haven't added any applications to your tracker yet.")
        if st.button("💼 Browse Jobs to Apply"):
            st.session_state.page = "jobs"
            st.rerun()
        return

    # Metrics summary
    total = len(applications)
    interviews = sum(1 for a in applications if a.get("status") == "interview_scheduled")
    offers = sum(1 for a in applications if a.get("status") == "offer")
    active = sum(1 for a in applications if a.get("status") not in ("offer", "rejected", "withdrawn"))

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Tracked", total)
    with m2:
        st.metric("Active Processes", active)
    with m3:
        st.metric("Interviews Scheduled", interviews)
    with m4:
        st.metric("Offers Received", offers)

    st.divider()

    st.subheader("Your Applications")

    # Fetch jobs dictionary to display titles
    jobs_res = api_client.list_jobs(limit=100)
    jobs_map = {}
    if jobs_res["ok"] and isinstance(jobs_res["data"], list):
        jobs_map = {j["id"]: j for j in jobs_res["data"]}

    for app in applications:
        app_id = app["id"]
        job_id = app["job_id"]
        job_info = jobs_map.get(job_id, {})
        job_title = job_info.get("title", f"Job #{job_id}")
        company = job_info.get("company_name", "Direct")

        current_status = app.get("status", "draft")

        with st.expander(f"**{job_title}** @ {company} — Status: `{current_status.upper()}`", expanded=True):
            col_info, col_form = st.columns([1, 1])

            with col_info:
                st.markdown(f"**Application ID:** `{app_id}`")
                st.markdown(f"**Job ID:** `{job_id}`")
                created_at = (app.get("created_at") or "")[:19].replace("T", " ")
                updated_at = (app.get("updated_at") or "")[:19].replace("T", " ")
                st.caption(f"Created: {created_at} • Last Updated: {updated_at}")

                if app.get("confirmation_reference"):
                    st.success(f"Receipt / Ref: `{app.get('confirmation_reference')}`")

                if app.get("notes"):
                    st.info(f"📝 **Notes:** {app.get('notes')}")

            with col_form:
                st.markdown("##### Update Status")
                with st.form(f"update_app_form_{app_id}"):
                    curr_idx = STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0
                    new_status = st.selectbox(
                        "Change Status",
                        options=STATUS_OPTIONS,
                        index=curr_idx,
                        key=f"status_select_{app_id}",
                    )
                    new_notes = st.text_input(
                        "Update Notes",
                        value=app.get("notes") or "",
                        key=f"notes_input_{app_id}",
                    )
                    conf_ref = st.text_input(
                        "Confirmation Reference (required for submitted_confirmed)",
                        value=app.get("confirmation_reference") or "",
                        key=f"conf_ref_{app_id}",
                    )

                    save_btn = st.form_submit_button("Update Application", use_container_width=True)

                    if save_btn:
                        payload = {}
                        if new_status != current_status:
                            payload["status"] = new_status
                        if new_notes != (app.get("notes") or ""):
                            payload["notes"] = new_notes
                        if conf_ref != (app.get("confirmation_reference") or ""):
                            payload["confirmation_reference"] = conf_ref

                        if not payload:
                            st.info("No changes to update.")
                        else:
                            with st.spinner("Updating status..."):
                                up_res = api_client.update_application(app_id, payload)

                            if up_res["ok"]:
                                st.success("Application updated successfully!")
                                st.rerun()
                            else:
                                detail = up_res["data"].get("detail", "Update failed.")
                                st.error(f"Error: {detail}")
