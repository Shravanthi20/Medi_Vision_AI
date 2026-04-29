import os

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
