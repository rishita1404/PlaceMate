"""
app/ui/pages/resume.py
──────────────────────
Resume Upload & Text Extraction view.
"""

import streamlit as st
from app.ui import api_client


def render():
    st.title("📄 Resume Upload & Parser")
    st.markdown("Upload your existing PDF resume to inspect and extract structured information.")

    # ── Upload Section ──
    st.subheader("📤 Upload New Resume")
    uploaded_file = st.file_uploader(
        "Choose a PDF file (Text-based PDF, max 10MB)",
        type=["pdf"],
        help="Make sure the PDF contains selectable text (not a scanned image/photo).",
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name

        col_u1, _ = st.columns([2, 3])
        with col_u1:
            if st.button("🚀 Upload & Parse Resume", type="primary", use_container_width=True):
                with st.spinner("Uploading resume to secure storage..."):
                    res = api_client.upload_resume(file_bytes, file_name)

                if res["ok"]:
                    resume_id = res["data"]["id"]
                    st.success(f"Resume uploaded successfully! (ID: {resume_id})")

                    with st.spinner("Extracting text with PyMuPDF..."):
                        ext_res = api_client.extract_resume(resume_id)

                    if ext_res["ok"]:
                        ext_data = ext_res["data"]
                        st.balloons()
                        st.success(f"✅ {ext_data.get('message', 'Text extracted successfully!')}")
                        st.info(f"Pages detected: {ext_data.get('page_count', 1)}")

                        preview = ext_data.get("extracted_text_preview", "")
                        if preview:
                            st.markdown("#### 📝 Extracted Text Preview:")
                            st.text_area("Preview (first 500 characters)", value=preview, height=180, disabled=True)
                            st.caption("You can use this extracted content to fill in your skills and experience on the My Profile page.")
                    else:
                        st.warning(f"Uploaded, but extraction had an issue: {ext_res['data'].get('detail', 'Extraction error')}")
                else:
                    detail = res["data"].get("detail", "Upload failed")
                    st.error(f"Upload failed: {detail}")

    st.divider()

    # ── Previous Resumes ──
    st.subheader("📚 Upload History")
    list_res = api_client.list_resumes()
    if not list_res["ok"]:
        st.error(f"Could not load resumes: {list_res['data'].get('detail', 'Unknown error')}")
        return

    resumes = list_res["data"]
    if not resumes:
        st.info("You haven't uploaded any resumes yet.")
    else:
        for r in resumes:
            with st.container():
                rc1, rc2, rc3 = st.columns([3, 2, 2])
                with rc1:
                    st.markdown(f"**📄 {r.get('original_filename')}**")
                    size_kb = round(r.get("file_size_bytes", 0) / 1024, 1)
                    st.caption(f"Size: {size_kb} KB • Uploaded: {(r.get('uploaded_at') or '')[:10]}")
                with rc2:
                    status_val = r.get("status")
                    if status_val == "extracted":
                        st.success(f"Status: {status_val.upper()} ({r.get('page_count', 1)} pages)")
                    elif status_val == "failed":
                        st.error(f"Status: {status_val.upper()}")
                        if r.get("error_message"):
                            st.caption(f"Reason: {r.get('error_message')}")
                    else:
                        st.info(f"Status: {status_val.upper()}")
                with rc3:
                    if r.get("status") in ("uploaded", "failed"):
                        if st.button("Extract Now", key=f"re_extract_{r.get('id')}", use_container_width=True):
                            with st.spinner("Extracting..."):
                                e_res = api_client.extract_resume(r.get("id"))
                                if e_res["ok"]:
                                    st.success("Extraction completed!")
                                    st.rerun()
                                else:
                                    st.error(e_res["data"].get("detail", "Failed"))
                st.write("---")
