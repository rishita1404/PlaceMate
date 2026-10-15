"""
app/ui/pages/jobs.py
───────────────────
Browse jobs, compute explainable match scores, verify eligibility,
review interview questions, and initiate applications.
"""

import streamlit as st
from app.ui import api_client


def render():
    st.title("💼 Browse Job Opportunities")
    st.markdown("Explore verified opportunities, see transparent match breakdowns, and prepare for interviews.")

    # ── Filter Row ──
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        type_filter = st.selectbox(
            "Filter by Job Type",
            options=["All Types", "internship", "full_time", "part_time", "contract"],
            format_func=lambda x: x.replace("_", " ").title() if x != "All Types" else x,
        )
    with col_f2:
        loc_search = st.text_input("Search Location", placeholder="e.g. Pune, Bangalore, Hybrid, Remote")

    # Fetch jobs
    with st.spinner("Fetching active jobs..."):
        job_type_param = None if type_filter == "All Types" else type_filter
        loc_param = loc_search.strip() if loc_search.strip() else None

        # Call API through api_client
        res = api_client.list_jobs(limit=100)

    if not res["ok"]:
        st.error(f"Could not load jobs: {res['data'].get('detail', 'Unknown error')}")
        return

    jobs = res["data"]
    if not isinstance(jobs, list):
        jobs = []

    # Filter in memory if query params weren't handled by list_jobs directly
    if job_type_param:
        jobs = [j for j in jobs if j.get("job_type") == job_type_param]
    if loc_param:
        jobs = [j for j in jobs if loc_param.lower() in (j.get("location") or "").lower()]

    st.write(f"Showing **{len(jobs)}** active opportunities")

    if not jobs:
        st.info("No matching jobs found. Try adjusting your search filters.")
        return

    st.write("")

    # Determine currently selected job
    selected_id = st.session_state.get("selected_job_id", jobs[0]["id"] if jobs else None)

    # ── Two-column layout: Job List on Left, Detail & AI Analysis on Right ──
    col_list, col_detail = st.columns([2, 3])

    with col_list:
        st.subheader("Opportunities")
        for j in jobs:
            jid = j["id"]
            is_active = jid == selected_id

            card_border = "border: 2px solid #3b82f6;" if is_active else "border: 1px solid #e2e8f0;"
            st.markdown(
                f"""
                <div style="padding: 12px; margin-bottom: 8px; border-radius: 8px; {card_border}">
                    <h4 style="margin: 0; padding: 0;">{j.get('title')}</h4>
                    <p style="margin: 4px 0; color: #64748b; font-size: 0.9em;">
                        🏢 {j.get('company_name') or 'Direct'} • 📍 {j.get('location', 'Unspecified')}
                    </p>
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; background: #e0f2fe; color: #0369a1; font-weight: 600;">
                        {(j.get('job_type') or 'N/A').replace('_', ' ').upper()}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Select Job #{jid}", key=f"sel_btn_{jid}", use_container_width=True):
                st.session_state.selected_job_id = jid
                st.rerun()

    with col_detail:
        if not selected_id:
            st.info("Select a job from the left to view details and analysis.")
            return

        detail_res = api_client.get_job(selected_id)
        if not detail_res["ok"]:
            st.error("Failed to load job details.")
            return

        job = detail_res["data"]
        st.subheader(f"📋 {job.get('title')}")

        meta_c1, meta_c2 = st.columns(2)
        with meta_c1:
            st.caption(f"📍 Location: **{job.get('location', 'Unspecified')}**")
            st.caption(f"💼 Type: **{(job.get('job_type') or 'N/A').replace('_', ' ').title()}**")
        with meta_c2:
            deadline = (job.get("deadline") or "")[:10] if job.get("deadline") else "Rolling admission"
            st.caption(f"⏰ Deadline: **{deadline}**")
            if job.get("official_url"):
                st.markdown(f"🔗 [Official Job Post]({job.get('official_url')})")

        st.write("")
        st.markdown("#### Description")
        st.write(job.get("description") or "No detailed description provided.")

        st.write("")
        st.markdown("#### Skills & Criteria")
        req_skills = job.get("required_skills") or []
        pref_skills = job.get("preferred_skills") or []

        if req_skills:
            st.markdown("**Required Skills:** " + ", ".join([f"`{s}`" for s in req_skills]))
        if pref_skills:
            st.markdown("**Preferred Skills:** " + ", ".join([f"`{s}`" for s in pref_skills]))

        st.divider()

        # ── Interactive Feature Tabs ──
        tab_match, tab_elig, tab_prep, tab_apply = st.tabs([
            "🎯 Match Analysis",
            "✔️ Eligibility Check",
            "💡 Interview Prep",
            "🚀 Application Draft",
        ])

        # ── Tab 1: Match Analysis ──
        with tab_match:
            st.markdown("##### Explainable Match Score")
            st.caption("Deterministic scoring based on required skills (50%), preferred skills (20%), and experience (30%).")

            if st.button("📊 Calculate My Match Score", key=f"calc_match_{selected_id}", use_container_width=True):
                with st.spinner("Analyzing match against your confirmed profile..."):
                    m_res = api_client.get_match(selected_id)

                if m_res["ok"]:
                    m_data = m_res["data"]
                    score = m_data.get("overall_score", 0.0)
                    st.metric("Overall Match Score", f"{score}%")
                    st.progress(min(1.0, score / 100.0))

                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        st.caption(f"Required Skills: **{m_data.get('required_skill_score', 0)}%**")
                    with sc2:
                        st.caption(f"Preferred Skills: **{m_data.get('preferred_skill_score', 0)}%**")
                    with sc3:
                        st.caption(f"Experience: **{m_data.get('experience_score', 0)}%**")

                    st.write("")
                    detail = m_data.get("skill_detail", {})
                    matched_req = detail.get("matched_required", [])
                    missing_req = detail.get("missing_required", [])

                    if matched_req:
                        st.success(f"✅ Matched Required Skills: {', '.join(matched_req)}")
                    if missing_req:
                        st.error(f"❌ Missing Required Skills: {', '.join(missing_req)}")

                    explanation = m_data.get("score_explanation")
                    if explanation:
                        st.info(f"💡 **Explanation:** {explanation}")

                    supp = m_data.get("supporting_projects") or []
                    if supp:
                        st.markdown(f"**Supporting Projects Found:** {', '.join(supp)}")
                else:
                    detail_err = m_res["data"].get("detail", "Calculation failed")
                    st.warning(f"⚠️ {detail_err}")
                    if "confirmed" in detail_err.lower():
                        st.info("Head to the **My Profile** tab and click **Confirm Profile** to unlock tailored matching.")

        # ── Tab 2: Eligibility Check ──
        with tab_elig:
            st.markdown("##### Verification & Eligibility Rules")
            if st.button("🔍 Check My Eligibility", key=f"calc_elig_{selected_id}", use_container_width=True):
                with st.spinner("Checking eligibility rules..."):
                    el_res = api_client.get_eligibility(selected_id)

                if el_res["ok"]:
                    el_data = el_res["data"]
                    overall_gen = el_data.get("overall_general", "unknown")
                    badge_color = "green" if overall_gen == "eligible" else ("red" if overall_gen == "ineligible" else "orange")
                    st.markdown(f"General Status: **:{badge_color}[{overall_gen.upper()}]**")

                    general_checks = el_data.get("general_checks", [])
                    for check in general_checks:
                        res_str = check.get("result", "")
                        icon = "✅" if res_str == "pass" else ("❌" if res_str == "fail" else "❓")
                        st.write(f"{icon} **{check.get('criterion')}**: {check.get('reason')}")

                    college_checks = el_data.get("college_checks", [])
                    if college_checks:
                        st.markdown("###### College-Specific Checks")
                        for c in college_checks:
                            st.write(f"• **{c.get('criterion')}**: {c.get('reason')}")
                    else:
                        st.caption("No college-specific restrictions applied for this opening.")

                    if el_data.get("note"):
                        st.caption(f"Note: {el_data.get('note')}")
                else:
                    st.error(el_res["data"].get("detail", "Eligibility check failed."))

        # ── Tab 3: Interview Prep ──
        with tab_prep:
            st.markdown("##### Interview Preparation Questions")
            if st.button("💡 Load Interview Questions", key=f"calc_prep_{selected_id}", use_container_width=True):
                with st.spinner("Retrieving verified and practice questions..."):
                    q_res = api_client.get_interview_questions(selected_id)

                if q_res["ok"]:
                    q_data = q_res["data"]
                    st.caption(f"📢 *{q_data.get('disclaimer', '')}*")

                    source_backed = q_data.get("source_backed", [])
                    unverified = q_data.get("unverified", [])
                    ai_gen = q_data.get("ai_generated", [])

                    if source_backed:
                        st.markdown("###### 🛡️ Verified Past Interview Questions")
                        for q in source_backed:
                            st.markdown(f"- **{q.get('question_text')}**")
                            st.caption(f"Category: {q.get('question_category', 'General')} | Source: {q.get('source_url', 'Verified alumni archive')}")

                    if ai_gen:
                        st.markdown("###### 🤖 Practice Questions")
                        for q in ai_gen:
                            st.markdown(f"- **{q.get('question_text')}**")
                            st.caption(f"Category: {q.get('question_category', 'Technical')}")

                    if unverified:
                        st.markdown("###### 💬 Unverified Community Submissions")
                        for q in unverified:
                            st.markdown(f"- {q.get('question_text')}")

                    if not source_backed and not ai_gen and not unverified:
                        st.info("No curated questions available for this role yet.")
                else:
                    st.error(q_res["data"].get("detail", "Failed to retrieve questions."))

        # ── Tab 4: Application Draft ──
        with tab_apply:
            st.markdown("##### Save to Application Tracker")
            st.caption("Track your status through draft, submission, interview rounds, and offers.")

            app_notes = st.text_area("Personal Notes / Deadlines", placeholder="e.g. Need to review React hooks before technical round", key=f"app_notes_{selected_id}")
            if st.button("➕ Add to Application Tracker", key=f"create_app_{selected_id}", type="primary", use_container_width=True):
                with st.spinner("Creating application tracker record..."):
                    c_app_res = api_client.create_application(selected_id, app_notes)

                if c_app_res["ok"]:
                    st.success("🎉 Added to your Application Tracker! Visit the Tracker page to manage status updates.")
                else:
                    detail = c_app_res["data"].get("detail", "Failed to create application.")
                    st.warning(f"Note: {detail}")
