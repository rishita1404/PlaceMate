"""
tests/test_auth.py
──────────────────
Tests for registration, login, and access control.
"""

import pytest
from tests.conftest import auth_headers, register_and_login


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "securepass1"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["role"] == "student"
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "securepass1"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client):
    response = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "mypassword1"},
    )
    response = await client.post(
        "/auth/login",
        data={"username": "login@example.com", "password": "mypassword1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register",
        json={"email": "wrongpw@example.com", "password": "correctpassword"},
    )
    response = await client.post(
        "/auth/login",
        data={"username": "wrongpw@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client):
    """Profile endpoint must reject requests without a token."""
    response = await client.get("/profile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_profile_with_valid_token(client):
    """Authenticated student must be able to access their profile."""
    token = await register_and_login(client, "prof@example.com", "mypassword1")
    response = await client.get("/profile", headers=auth_headers(token))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_endpoint_rejected_for_student(client):
    """Admin endpoint must return 403 for a regular student."""
    token = await register_and_login(client, "student@example.com", "mypassword1")
    response = await client.get("/admin/college-rules", headers=auth_headers(token))
    assert response.status_code == 403
