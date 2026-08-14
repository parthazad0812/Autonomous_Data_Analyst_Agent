"""
Pytest configuration & fixtures for the backend test suite.
"""

import io
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
from app.services.auth_service import hash_password, create_access_token
from app.models.user import User

# Use an in-memory SQLite database for isolated fast unit tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh in-memory database schema for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database dependency."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a standard test user in the database."""
    user = User(
        email="test_user@example.com",
        hashed_password=hash_password("Password123!"),
        full_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Generate JWT authentication headers for test_user."""
    token = create_access_token(data={"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_csv_file() -> tuple[str, io.BytesIO, str]:
    """Sample CSV file buffer for upload endpoint testing."""
    csv_content = (
        "month,product,region,sales,units\n"
        "Jan,Laptop,North,52000,20\n"
        "Jan,Phone,South,38000,95\n"
        "Feb,Laptop,North,61000,22\n"
        "Feb,Phone,South,42000,105\n"
    )
    file_bytes = io.BytesIO(csv_content.encode("utf-8"))
    return ("sample_data.csv", file_bytes, "text/csv")
