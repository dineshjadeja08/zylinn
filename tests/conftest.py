# tests/conftest.py
import pytest
import sys
import os
from unittest.mock import patch

# Ensure correct paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent'))


@pytest.fixture(autouse=True)
def skip_if_no_db(request):
    """
    Skip integration tests if INTEGRATION_USE_REAL_DB is not set.
    The integration tests require PostgreSQL due to ARRAY types.
    """
    if "integration" in request.node.nodeid and os.getenv("INTEGRATION_USE_REAL_DB", "0") != "1":
        pytest.skip("Integration tests require PostgreSQL (INTEGRATION_USE_REAL_DB=1)")


@pytest.fixture(autouse=True, scope='session')
def mock_create_tables():
    """Mock DatabaseManager.create_tables to avoid SQLite ARRAY errors in unit tests."""
    with patch('models.DatabaseManager.create_tables', return_value=None):
        yield
