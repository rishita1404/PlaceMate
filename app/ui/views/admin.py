"""
app/ui/pages/admin.py
────────────────────
Admin control panel: manual job importation and college eligibility rules management.
"""

import streamlit as st
from app.ui import api_client


def render():
    st.title("⚙️ Admin Management Console")

    user = st.session_state.get("user") or {}
    role = user.get("role", "student")

    if role != "admin":
        st.error("⛔ Access Denied. This section requires an administrator account.")
        st.info("Log in with an account having role='admin' to access management utilities.")
        return

    tab_import, tab_rules = st.tabs(["📥 Import Job Listing", "🏫 College Rules Management"])

    # ── Tab 1: Manual Job Import ──
    with tab_import:
        st.subheader("Manually Import Job Listing")
        with st.form("form_admin_import_job"):
            col1, col2 = st.columns(2)
            with col1:
                company_name = st.text_input("Company Name *", placeholder="e.g. Acme Technologies")
                job_title = st.text_input("Job Title *", placeholder="e.g. Associate Software Engineer")
                location = st.text_input("Location", placeholder="e.g. Pune, India (Hybrid)")
                job_type = st.selectbox(
                    "Job Type",
                    options=["internship", "full_time", "part_time", "contract"],
                    format_func=lambda x: x.replace("_", " ").title(),
                )
            with col2:
                official_url = st.text_input("Official Careers URL", placeholder="https://careers.acme.com/job/123")
                req_skills_in = st.text_input("Required Skills (comma-separated)", placeholder="Python, SQL, FastApi")
                pref_skills_in = st.text_input("Preferred Skills (comma-separated)", placeholder="Docker, AWS, Redis")
                deadline_str = st.date_input("Deadline", value=None)

            description = st.text_area("Job Description", placeholder="Job role overview, responsibilities...")

            st.write("")
            submit_job = st.form_submit_button("Import Job", use_container_width=True)

            if submit_job:
                if not company_name or not job_title:
                    st.error("Company Name and Job Title are required.")
                else:
                    req_list = [s.strip() for s in req_skills_in.split(",") if s.strip()]
                    pref_list = [s.strip() for s in pref_skills_in.split(",") if s.strip()]

                    payload = {
                        "company_name": company_name,
                        "title": job_title,
                        "description": description or None,
                        "location": location or None,
                        "job_type": job_type,
                        "required_skills": req_list,
                        "preferred_skills": pref_list,
                        "official_url": official_url or None,
                        "deadline": deadline_str.isoformat() if deadline_str else None,
                        "eligibility_requirements": {},
                    }

                    with st.spinner("Importing job listing..."):
                        res = api_client.admin_import_job(payload)

                    if res["ok"]:
                        st.success(f"🎉 Job '{job_title}' successfully imported with ID #{res['data']['id']}!")
                    else:
                        st.error(f"Import failed: {res['data'].get('detail', 'Unknown error')}")

    # ── Tab 2: College Rules Management ──
    with tab_rules:
        st.subheader("Placement Eligibility Rules")
        st.caption("Define college-specific placement constraints and verify their authenticity.")

        # Add New Rule
        with st.expander("➕ Add New Placement Rule", expanded=False):
            with st.form("form_create_rule"):
                rc1, rc2 = st.columns(2)
                with rc1:
                    college_scope = st.text_input("College / Dept Scope", placeholder="e.g. COEP-CSE, VIT-IT")
                    rule_type = st.selectbox(
                        "Rule Type",
                        options=["min_cgpa", "backlog_limit", "stream_restriction", "tier_rule"],
                    )
                with rc2:
                    rule_value = st.text_input("Rule Value", placeholder="e.g. 7.5, 0, BTech only")
                    source_ref = st.text_input("Source Reference", placeholder="Circular #102/2026")

                submit_rule = st.form_submit_button("Create Rule", use_container_width=True)
                if submit_rule:
                    if not college_scope or not rule_value:
                        st.error("Scope and Value are required.")
                    else:
                        rule_payload = {
                            "college_scope": college_scope,
                            "rule_type": rule_type,
                            "rule_value": rule_value,
                            "source_reference": source_ref or None,
                        }
                        r_res = api_client.admin_create_college_rule(rule_payload)
                        if r_res["ok"]:
                            st.success("Rule created!")
                            st.rerun()
                        else:
                            st.error(r_res["data"].get("detail", "Failed to create rule."))

        st.write("")
        st.markdown("#### Existing Rules")
        rules_res = api_client.admin_list_college_rules()
        if not rules_res["ok"]:
            st.error(rules_res["data"].get("detail", "Failed to load rules."))
            return

        rules = rules_res["data"]
        if not rules:
            st.info("No college placement rules recorded yet.")
        else:
            for rule in rules:
                rid = rule["id"]
                status_v = rule.get("verification_status", "pending")
                badge_color = "green" if status_v == "verified" else "orange"

                with st.container():
                    rcol1, rcol2, rcol3 = st.columns([3, 2, 2])
                    with rcol1:
                        st.markdown(f"**Scope:** `{rule.get('college_scope')}` — {rule.get('rule_type')}")
                        st.caption(f"Value: `{rule.get('rule_value')}` | Ref: {rule.get('source_reference') or 'None'}")
                    with rcol2:
                        st.markdown(f"Status: **:{badge_color}[{status_v.upper()}]**")
                        if rule.get("verified_by"):
                            st.caption(f"By: {rule.get('verified_by')}")
                    with rcol3:
                        if status_v != "verified":
                            if st.button("Verify Rule", key=f"verify_rule_{rid}"):
                                v_res = api_client.admin_verify_college_rule(
                                    rid,
                                    {"verified_by": user.get("email", "admin")},
                                )
                                if v_res["ok"]:
                                    st.success("Verified!")
                                    st.rerun()
                                else:
                                    st.error("Verification failed.")
                        if st.button("Delete", key=f"del_rule_{rid}"):
                            del_res = api_client.admin_delete_college_rule(rid)
                            if del_res["ok"]:
                                st.warning("Deleted!")
                                st.rerun()
                            else:
                                st.error("Delete failed.")
                    st.write("---")
