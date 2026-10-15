"""
app/ui/api_client.py
─────────────────────
Thin HTTP client that wraps all calls to the FastAPI backend.

All UI pages call functions here instead of making requests directly.
This means if the backend URL changes, there is only one place to update.
"""

import streamlit as st
import httpx
from typing import Optional

API_BASE = "http://127.0.0.1:8002"
TIMEOUT = 15.0


def _headers(token: Optional[str] = None) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _token() -> Optional[str]:
    return st.session_state.get("token")


# ── Auth ──────────────────────────────────────────────────────────────────────

def register(email: str, password: str) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/auth/register",
            json={"email": email, "password": password},
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 201, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Cannot reach the backend. Is it running?"}, "status": 0}


def login(email: str, password: str) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Cannot reach the backend. Is it running?"}, "status": 0}


# ── Health ────────────────────────────────────────────────────────────────────

def health() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5.0)
        return r.json()
    except Exception:
        return {"status": "unreachable", "database": "unknown", "ai_enabled": False}


# ── Profile ───────────────────────────────────────────────────────────────────

def get_profile() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/profile", headers=_headers(_token()), timeout=TIMEOUT)
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def update_profile(payload: dict) -> dict:
    try:
        r = httpx.put(
            f"{API_BASE}/profile",
            json=payload,
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def confirm_profile() -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/profile/confirm",
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


# ── Resumes ───────────────────────────────────────────────────────────────────

def upload_resume(file_bytes: bytes, filename: str) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/resumes/upload",
            files={"file": (filename, file_bytes, "application/pdf")},
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=30.0,
        )
        return {"ok": r.status_code == 201, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def extract_resume(resume_id: int) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/resumes/{resume_id}/extract",
            headers=_headers(_token()),
            timeout=30.0,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def list_resumes() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/resumes", headers=_headers(_token()), timeout=TIMEOUT)
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


# ── Jobs ──────────────────────────────────────────────────────────────────────

def list_jobs(skip: int = 0, limit: int = 20) -> dict:
    try:
        r = httpx.get(
            f"{API_BASE}/jobs",
            params={"skip": skip, "limit": limit},
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def get_job(job_id: int) -> dict:
    try:
        r = httpx.get(f"{API_BASE}/jobs/{job_id}", headers=_headers(_token()), timeout=TIMEOUT)
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def get_match(job_id: int) -> dict:
    try:
        r = httpx.get(f"{API_BASE}/jobs/{job_id}/match", headers=_headers(_token()), timeout=TIMEOUT)
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def get_eligibility(job_id: int) -> dict:
    try:
        r = httpx.get(f"{API_BASE}/jobs/{job_id}/eligibility", headers=_headers(_token()), timeout=TIMEOUT)
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def get_interview_questions(job_id: int) -> dict:
    try:
        r = httpx.get(
            f"{API_BASE}/jobs/{job_id}/interview-questions",
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


# ── Applications ──────────────────────────────────────────────────────────────

def create_application(job_id: int, notes: str = "") -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/applications",
            json={"job_id": job_id, "notes": notes or None},
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 201, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def list_applications() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/applications", headers=_headers(_token()), timeout=TIMEOUT)
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def update_application(app_id: int, payload: dict) -> dict:
    try:
        r = httpx.patch(
            f"{API_BASE}/applications/{app_id}",
            json=payload,
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


# ── Admin ─────────────────────────────────────────────────────────────────────

def admin_import_job(payload: dict) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/admin/jobs/import",
            json=payload,
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 201, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def admin_list_college_rules() -> dict:
    try:
        r = httpx.get(
            f"{API_BASE}/admin/college-rules",
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def admin_create_college_rule(payload: dict) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/admin/college-rules",
            json=payload,
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 201, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def admin_verify_college_rule(rule_id: int, payload: dict) -> dict:
    try:
        r = httpx.post(
            f"{API_BASE}/admin/college-rules/{rule_id}/verify",
            json=payload,
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}


def admin_delete_college_rule(rule_id: int) -> dict:
    try:
        r = httpx.delete(
            f"{API_BASE}/admin/college-rules/{rule_id}",
            headers=_headers(_token()),
            timeout=TIMEOUT,
        )
        return {"ok": r.status_code == 200, "data": r.json(), "status": r.status_code}
    except httpx.ConnectError:
        return {"ok": False, "data": {"detail": "Backend unreachable."}, "status": 0}

