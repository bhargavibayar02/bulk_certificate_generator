"""
Pytest Test Fixtures and Configuration.

Configures an isolated SQLite in-memory database and FastAPI TestClient
for executing automated tests without touching development/production databases.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

# Create in-memory SQLite engine for testing with StaticPool so all threads share the memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Initializes the schema in the test database once per test session.
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def patch_job_processor_session(monkeypatch):
    """
    Points the background job processor to the in-memory test database session factory.
    """
    import app.services.job_processor
    monkeypatch.setattr(app.services.job_processor, "SessionLocal", TestingSessionLocal)


@pytest.fixture
def db_session():
    """
    Provides a clean, transaction-isolated database session for each test.
    Rolls back any modifications after the test finishes.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """
    FastAPI TestClient fixture with overridden database dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
