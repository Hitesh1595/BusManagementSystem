"""
Test fixtures for the YatraTrack backend.

DB note: PostgreSQL + PostGIS is not running locally yet (Docker comes in Task 1.11).
The `client` fixture connects against the real app; the /health endpoint gracefully
reports db="down" when DB is unreachable — this is acceptable for the smoke test.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """
    Async HTTP client that drives the FastAPI app directly via ASGITransport
    (no real network; no running server required).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
