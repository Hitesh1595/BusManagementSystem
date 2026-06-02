"""
Smoke test for GET /health.

The DB and Redis are not running in local dev (Docker comes in Task 1.11),
so we assert only that the endpoint responds with a well-formed JSON body
containing the required keys.  Status code may be 200 (all up) or 503 (db down).
"""

import pytest


@pytest.mark.anyio
async def test_health_returns_expected_keys(client):
    r = await client.get("/health")
    assert r.status_code in {200, 503}, f"unexpected status {r.status_code}"
    body = r.json()
    assert "status" in body
    assert "db" in body
    assert "redis" in body
    assert "last_gps_event_at" in body


@pytest.mark.anyio
async def test_health_db_and_redis_values_are_strings(client):
    r = await client.get("/health")
    body = r.json()
    assert isinstance(body["db"], str)
    assert isinstance(body["redis"], str)
    assert body["db"] in {"connected", "down"}
    assert body["redis"] in {"connected", "degraded"}
