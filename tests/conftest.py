"""
Test fixtures.

DATABASE_URL must be set before any application import because the engine is
created at import time in agentmarket.models.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_agentmarket.db"
os.environ["DEBUG"] = "true"

import pytest
from fastapi.testclient import TestClient

from agentmarket.models import engine
from agentmarket.models.database import Base
from agentmarket.utils.rate_limit import limiter
from main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_db():
    """Give every test an empty database."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def rate_limits(request):
    """Disable rate limiting unless the test opts in with @pytest.mark.rate_limited."""
    limiter.reset()
    limiter.enabled = "rate_limited" in request.keywords
    yield
    limiter.enabled = True
    limiter.reset()


def pytest_sessionfinish(session, exitstatus):
    try:
        os.remove("test_agentmarket.db")
    except OSError:
        pass
