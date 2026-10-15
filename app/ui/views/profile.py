"""
app/ui/pages/profile.py
──────────────────────
Student Profile management: education, skills, projects, and confirmation.
"""

import streamlit as st
import json
from app.ui import api_client


def render():
    st.title("👤 My Career Profile")
    st.markdown("Keep your academic, skills, and project details up to date for precise matching.")

    res = api_client.get_profile()
    if not res["ok"]:
        st.error(f"Failed to load profile: {res['data'].get('detail', 'Unknown error')}")
        return

    profile = res["data"]
    is_confirmed = profile.get("is_confirmed", False)

    # ── Confirmation Status Header ──
    if is_confirmed:
        confirmed_at = (profile.get("confirmed_at") or "")[:19].replace("T", " ")
        st.success(f"✅ **Profile Confirmed** on {confirmed_at}. Ready for tailored matching and application drafts.")
    else:
        st.warning(
            "⚠️ **Profile Not Confirmed**\n\n"
            "PlaceMate AI requires you to confirm your profile data before using it for job matching and tailored applications. "
            "Please review the fields below and click **Confirm Profile**."
        )

    st.write("")

    # ── Edit Form ──
    with st.form("form_profile"):
        st.subheader("🎓 Education & Academics")
        col1, col2 = st.columns(2)
        with col1:
            institution = st.text_input("Institution / University", value=profile.get("institution") or "")
            degree = st.text_input("Degree (e.g., B.Tech, B.Sc, BCA, MBA)", value=profile.get("degree") or "")
            specialization = st.text_input("Specialization / Major", value=profile.get("specialization") or "")
        with col2:
            grad_year = st.number_input(
                "Graduation Year",
                min_value=2000,
                max_value=2035,
                value=int(profile.get("graduation_year") or 2025),
                step=1,
            )
            gcol1, gcol2 = st.columns(2)
            with gcol1:
                gpa_val = float(profile.get("gpa") or 0.0)
                gpa = st.number_input("GPA / Score", min_value=0.0, max_value=100.0, value=gpa_val, step=0.1)
            with gcol2:
                current_gpa_type = profile.get("gpa_type") or "gpa"
                gpa_type = st.selectbox(
                    "Score Scale",
                    options=["gpa", "percentage"],
                    index=0 if current_gpa_type == "gpa" else 1,
                )

        st.divider()

        st.subheader("🛠️ Technical & Professional Skills")
        st.caption("Enter comma-separated skills (e.g., Python, SQL, React, Git, Machine Learning)")
        current_skills = profile.get("skills") or []
        skills_str = st.text_area(
            "Skills",
            value=", ".join(current_skills),
            placeholder="Python, SQL, React, Docker, Communication",
            help="PlaceMate normalizes skill names for matching algorithms.",
        )

        st.divider()

        st.subheader("💼 Work & Internship Experience")
        st.caption("JSON or simplified structured record of internships and roles.")
        existing_exp = profile.get("experience") or []
        exp_json_str = json.dumps(existing_exp, indent=2)
        new_exp_str = st.text_area(
            "Experience (JSON format: [{\"company\": \"...\", \"role\": \"...\", \"description\": \"...\", \"is_internship\": true}])",
            value=exp_json_str,
            height=130,
        )

        st.divider()

        st.subheader("🚀 Projects")
        st.caption("Key academic and personal projects used to support your job applications.")
        existing_proj = profile.get("projects") or []
        proj_json_str = json.dumps(existing_proj, indent=2)
        new_proj_str = st.text_area(
            "Projects (JSON format: [{\"name\": \"...\", \"description\": \"...\", \"technologies\": [\"Python\", \"React\"]}])",
            value=proj_json_str,
            height=130,
        )

        st.divider()

        st.subheader("📜 Certifications & Preferences")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            current_certs = profile.get("certifications") or []
            certs_str = st.text_input(
                "Certifications (comma-separated)",
                value=", ".join(current_certs),
                placeholder="AWS Certified Practitioner, Google Cloud Associate",
            )
        with col_c2:
            existing_prefs = profile.get("preferences") or {}
            pref_role = existing_prefs.get("preferred_role", "")
            pref_location = existing_prefs.get("preferred_location", "")
            pref_role_in = st.text_input("Preferred Role", value=pref_role, placeholder="Frontend Engineer, SDE Intern")
            pref_loc_in = st.text_input("Preferred Location", value=pref_location, placeholder="Bangalore, Remote, Hybrid")

        st.write("")
        submit_save = st.form_submit_button("💾 Save Profile Changes", use_container_width=True)

        if submit_save:
            # Parse skills
            skills_list = [s.strip() for s in skills_str.split(",") if s.strip()]
            certs_list = [c.strip() for c in certs_str.split(",") if c.strip()]

            # Parse experience JSON
            try:
                parsed_exp = json.loads(new_exp_str) if new_exp_str.strip() else []
                if not isinstance(parsed_exp, list):
                    st.error("Experience must be a JSON list of objects.")
                    return
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON in Experience: {e}")
                return

            # Parse projects JSON
            try:
                parsed_proj = json.loads(new_proj_str) if new_proj_str.strip() else []
                if not isinstance(parsed_proj, list):
                    st.error("Projects must be a JSON list of objects.")
                    return
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON in Projects: {e}")
                return

            payload = {
                "institution": institution or None,
                "degree": degree or None,
                "specialization": specialization or None,
                "graduation_year": int(grad_year),
                "gpa": float(gpa) if gpa > 0 else None,
                "gpa_type": gpa_type,
                "skills": skills_list,
                "experience": parsed_exp,
                "projects": parsed_proj,
                "certifications": certs_list,
                "preferences": {
                    "preferred_role": pref_role_in,
                    "preferred_location": pref_loc_in,
                },
            }

            with st.spinner("Saving changes..."):
                update_res = api_client.update_profile(payload)
                if update_res["ok"]:
                    st.success("Profile saved successfully!")
                    st.rerun()
                else:
                    detail = update_res["data"].get("detail", "Save failed")
                    st.error(f"Error saving profile: {detail}")

    # ── Confirm Button Section ──
    st.write("")
    st.markdown("### 🎯 Final Confirmation")
    st.caption("Confirming your profile marks your records as student-verified truth.")

    c_btn, _ = st.columns([2, 3])
    with c_btn:
        if st.button("✅ Confirm My Profile Now", use_container_width=True, type="primary"):
            with st.spinner("Confirming profile..."):
                c_res = api_client.confirm_profile()
                if c_res["ok"]:
                    st.success("🎉 " + c_res["data"].get("message", "Profile confirmed!"))
                    st.rerun()
                else:
                    detail = c_res["data"].get("detail", "Confirmation failed")
                    st.error(f"Could not confirm: {detail}")
