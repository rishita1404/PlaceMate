"""
app/ui/pages/auth.py
───────────────────
Authentication page: Sign In & Registration.
"""

import streamlit as st
from jose import jwt
from app.ui import api_client


def render():
    st.markdown("## 🔐 Welcome to PlaceMate AI")
    st.markdown("Your AI-guided career companion for internships and placements.")
    st.write("")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_register = st.tabs(["🔑 Sign In", "✨ Create Account"])

        with tab_login:
            st.subheader("Sign In")
            with st.form("form_login"):
                email = st.text_input("Email", placeholder="student@example.edu").strip()
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign In", use_container_width=True)

                if submit:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        with st.spinner("Signing in..."):
                            res = api_client.login(email, password)
                            if res["ok"]:
                                token = res["data"]["access_token"]
                                st.session_state.token = token
                                try:
                                    claims = jwt.get_unverified_claims(token)
                                    role = claims.get("role", "student")
                                    user_id = claims.get("sub")
                                except Exception:
                                    role = "student"
                                    user_id = None

                                st.session_state.user = {
                                    "email": email,
                                    "role": role,
                                    "id": user_id,
                                }
                                st.success("Signed in successfully! Redirecting...")
                                st.session_state.page = "dashboard"
                                st.rerun()
                            else:
                                detail = res["data"].get("detail", "Sign in failed.")
                                st.error(f"Error: {detail}")

        with tab_register:
            st.subheader("Create a New Account")
            with st.form("form_register"):
                new_email = st.text_input("College / Personal Email", placeholder="student@example.edu").strip()
                new_password = st.text_input("Password (min 8 chars)", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                reg_submit = st.form_submit_button("Register", use_container_width=True)

                if reg_submit:
                    if not new_email or not new_password:
                        st.error("Please provide email and password.")
                    elif len(new_password) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        with st.spinner("Creating account..."):
                            res = api_client.register(new_email, new_password)
                            if res["ok"]:
                                st.success("Account created successfully! Signing in...")
                                login_res = api_client.login(new_email, new_password)
                                if login_res["ok"]:
                                    token = login_res["data"]["access_token"]
                                    st.session_state.token = token
                                    try:
                                        claims = jwt.get_unverified_claims(token)
                                        role = claims.get("role", "student")
                                        user_id = claims.get("sub")
                                    except Exception:
                                        role = "student"
                                        user_id = None
                                    st.session_state.user = {
                                        "email": new_email,
                                        "role": role,
                                        "id": user_id,
                                    }
                                    st.session_state.page = "profile"
                                    st.rerun()
                                else:
                                    st.info("Account created. Please log in using the Sign In tab.")
                            else:
                                detail = res["data"].get("detail", "Registration failed.")
                                st.error(f"Registration error: {detail}")
