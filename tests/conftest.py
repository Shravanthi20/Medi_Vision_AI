import os
import sys

# Ensure the project root is on the Python path so that imports like `backend` work when running tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from backend.app_factory import create_app


@pytest.fixture(scope="session")
def app():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("DATABASE_URL is required for API smoke tests")

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()
