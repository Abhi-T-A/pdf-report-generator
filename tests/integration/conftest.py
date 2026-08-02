"""
Integration test fixtures for tests that require a real PostgreSQL database.

These tests are automatically SKIPPED unless TEST_DATABASE_URL is configured:

    # .env
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/pdf_report_generator_test

Run only integration tests:
    pytest tests/integration/ -v

Skip integration tests:
    pytest tests/unit/ tests/api/ -v
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base


def _test_database_url() -> str | None:
    try:
        from app.core.config import settings
        return getattr(settings, "TEST_DATABASE_URL", None) or None
    except Exception:
        return None


@pytest.fixture(scope="session")
def integration_engine():
    """
    Session-scoped engine for integration tests.
    Creates all tables at the start of the session and drops them at the end.
    Skips the entire module if TEST_DATABASE_URL is not configured.
    """
    url = _test_database_url()
    if not url:
        pytest.skip(
            "Integration tests require TEST_DATABASE_URL.\n"
            "Add to .env:  TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/pdf_report_generator_test"
        )
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def integration_db(integration_engine):
    """Function-scoped session bound to the integration engine."""
    TestingSession = sessionmaker(
        bind=integration_engine,
        autoflush=False,
        autocommit=False,
    )
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
