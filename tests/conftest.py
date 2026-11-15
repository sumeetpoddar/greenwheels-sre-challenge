import os

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.core.database import initialize_database  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    initialize_database()
