"""
Root conftest.py — shared pytest configuration.

Test structure:
  tests/api/          — FastAPI route tests using SQLite in-memory DB
  tests/unit/         — Pure unit tests, no DB required
  tests/integration/  — Service/SQL tests against a real PostgreSQL test DB
                        (requires TEST_DATABASE_URL in .env)
"""
