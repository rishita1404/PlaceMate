"""
tests/test_health.py
────────────────────
Tests for the /health endpoint and basic database connectivity.
"""

import pytest


@pytest.mark.asyncio
async def test_health_ok(client):
    """Health endpoint must return 200 with status 'ok' when DB is reachable."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "ai_enabled" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """Health endpoint must be accessible without authentication."""
    response = await client.get("/health")
    assert response.status_code == 200
