import pytest

from db import Base, engine, SessionLocal
from db.models.user import User


# Recreate tables for all tests (ONE engine globally)
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Set up the database schema and drop/recreate tables before running any tests.
    """
    Base.metadata.drop_all(bind=engine)  # Drop any existing schema
    Base.metadata.create_all(bind=engine)  # Create fresh tables


# Use the shared global SessionLocal for test database access
@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def app():
    """
    Create and configure a Flask app for testing.
    """
    from api import create_app

    # Use the shared engine/session; pass test_mode=True or adjust as needed
    app = create_app(test_mode=True, debug=True)
    yield app


@pytest.fixture
def client(app):
    """
    Provide a Flask test client.
    """
    return app.test_client()


def test_register_user(client, db_session):
    """
    Test the /register endpoint for registering a new user.
    """
    # Prepare mock data to register a user
    mock_user = {"name": "John Doe", "username": "johndoe",  # enable pin logins
                 "auth_method": "pin", "pin": 1234}

    response = client.post("/register", json=mock_user)
    data = response.get_json()

    assert response.status_code == 201
    assert data["message"] == "User registered successfully"

    # Verify the user is in the database
    user = db_session.query(User).filter_by(username=mock_user["username"]).first()

    print(user)

    assert user is not None
    assert user.name == mock_user["name"]


def test_duplicate_user_registration(client, db_session):
    """
    Test registering a user with a username that already exists.
    """
    mock_user = {"name": "John Doe", "username": "johndoe.duplicate", "auth_method": "username"}

    # create the user 2x
    client.post("/register", json=mock_user)
    response = client.post("/register", json=mock_user)

    data = response.get_json()

    assert response.status_code == 409


def test_authenticate_user(client, db_session):
    """
    Test the /authenticate endpoint for user login.
    """

    # authenticate w/ user info
    login_data = {"username": "johndoe", "pin": 1234}
    response = client.post("/authenticate", json=login_data)
    data = response.get_json()

    assert response.status_code == 200


def test_authenticate_invalid_user(client, db_session):
    """
    Test authentication with an invalid username or password.
    """
    # Attempt to log in with invalid credentials
    invalid_login_data = {"username": "fake.username@example.com", "password": "wrongpassword"}
    response = client.post("/authenticate", json=invalid_login_data)
    data = response.get_json()

    assert response.status_code == 401


def test_logout_user(client):
    """
    Test the /logout endpoint (basic stub).
    """
    login_data = {"username": "johndoe", "pin": 1234}
    # authenticate prior to ensure clean logout
    client.post("/authenticate", json=login_data)
    response = client.post("/logout")
    data = response.get_json()

    assert response.status_code == 200
