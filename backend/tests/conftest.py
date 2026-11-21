import pytest
import os
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings
from backend.app.db import init_db

TEST_DB_PATH = "./test_app.db"


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
    monkeypatch.setattr(settings, "LLM_API_KEYS", "mock-key-1,mock-key-2")
    monkeypatch.setattr(settings, "ENABLE_FAILURE_SIMULATION", True)

    # Clean previous test db if exists
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    asyncio.run(init_db())

    yield

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
