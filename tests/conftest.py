import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA_DIR = PROJECT_ROOT / ".tmp"
TEST_DATA_DIR.mkdir(exist_ok=True)
TEST_DATABASE = TEST_DATA_DIR / "pytest-support.db"
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"

from app.db.session import Base, engine  # noqa: E402
from app.models import entities  # noqa: E402,F401


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
