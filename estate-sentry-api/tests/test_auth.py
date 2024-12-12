import pytest
from flask import Flask
from ..auth import auth_blueprint
from ..db.models.user import User
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from ..db.models.base import Base

# Set up an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create a new session factory for the test database
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=create_engine(TEST_DATABASE_URL))


@pytest.fixture
def app():
    """
    Create a new Flask test app with the `auth_blueprint` for testing.
    """
    app = Flask(__name__)
    app.register_blueprint(auth_blueprint)

    # Use the in-memory test database
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = TEST_DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize tables for the test database
    Base.metadata.create_all(bind=create_engine(TEST_DATABASE_URL))

    yield app

    # Drop all tables after the test is complete
    Base.metadata.drop_all(bind=create_engine(TEST_DATABASE_URL))


@pytest.fixture
def client(app):
    """
    Create a test client for the Flask app.
    """
    return app.test_client()


@pytest.fixture
def db_session():
    """
    Provide a transactional scope for SQLAlchemy session.
    """
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_register_user(client, db_session):
    """
    Test the /register endpoint for registering a new user.
    """
    # Prepare mock data to register a user
    mock_user = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "password": "password123"
    }

    response = client.post("/register", json=mock_user)
    data = response.get_json()

    assert response.status_code == 201
    assert data["message"] == "User registered successfully"

    # Verify the user is in the database
    user = db_session.query(User).filter_by(email=mock_user["email"]).first()
    assert user is not None
    assert user.name == mock_user["name"]


def test_duplicate_user_registration(client, db_session):
    """
    Test registering a user with an email that already exists.
    """
    mock_user = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "password": "password123"
    }

    # Create the user
    client.post("/register", json=mock_user)

    # Attempt to create a duplicate user
    response = client.post("/register", json=mock_user)
    data = response.get_json()

    assert response.status_code == 409
    assert data["message"] == "Email is already registered"


def test_authenticate_user(client, db_session):
    """
    Test the /authenticate endpoint for user login.
    """
    # Register a user first
    mock_user = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "password": "password123"
    }
    client.post("/register", json=mock_user)

    # Attempt to authenticate the user
    login_data = {
        "email": "john.doe@example.com",
        "password": "password123"
    }
    response = client.post("/authenticate", json=login_data)
    data = response.get_json()

    assert response.status_code == 200
    assert data["message"] == "Authentication successful"
    assert "user_id" in data


def test_authenticate_invalid_user(client, db_session):
    """
    Test authentication with an invalid email or password.
    """
    # Attempt to login with invalid credentials
    invalid_login_data = {
        "email": "fake.email@example.com",
        "password": "wrongpassword"
    }
    response = client.post("/authenticate", json=invalid_login_data)
    data = response.get_json()

    assert response.status_code == 401
    assert data["message"] == "Invalid email or password"


def test_logout_user(client):
    """
    Test the /logout endpoint (basic stub).
    """
    response = client.post("/logout")
    data = response.get_json()

    assert response.status_code == 200
    assert data["message"] == "User logged out"
