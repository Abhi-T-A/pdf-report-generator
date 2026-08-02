"""
API test fixtures — uses SQLite in-memory to isolate tests from the real database.

Key design:
- A single in-memory engine is created per test.
- The `client` fixture overrides FastAPI's `get_db` to always return a session
  bound to that same engine, so tables created via Base.metadata.create_all
  are visible to both the test code and FastAPI route handlers.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app

SQLITE_TEST_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    """
    Create a fresh SQLite in-memory engine for one test.
    Uses check_same_thread=False so the engine can be shared across threads
    (FastAPI TestClient runs in a thread pool internally).
    """
    engine = create_engine(
        SQLITE_TEST_URL,
        connect_args={"check_same_thread": False},
    )
    # Keep a single connection open for the lifetime of the engine so the
    # in-memory database is not destroyed between sessions.
    connection = engine.connect()
    Base.metadata.create_all(bind=connection)

    yield engine, connection

    Base.metadata.drop_all(bind=connection)
    connection.close()
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Session bound to the isolated in-memory engine."""
    engine, connection = test_engine
    TestingSession = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
    )
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(test_engine):
    """
    FastAPI TestClient whose `get_db` dependency is overridden to use the same
    SQLite in-memory connection as `test_db`. Clears overrides after each test.
    """
    engine, connection = test_engine
    TestingSession = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
