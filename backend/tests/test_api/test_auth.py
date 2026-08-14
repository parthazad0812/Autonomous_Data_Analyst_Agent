"""
Integration tests for Authentication API endpoints (/api/v1/auth).
"""

from fastapi.testclient import TestClient


def test_register_user_success(client: TestClient):
    """Test registering a new user."""
    payload = {
        "email": "new_user@example.com",
        "password": "Password123!",
        "full_name": "New User",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "new_user@example.com"
    assert data["user"]["full_name"] == "New User"
    assert "id" in data["user"]


def test_register_duplicate_email_fails(client: TestClient):
    """Test registering with an existing email returns 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "password": "Password123!",
        "full_name": "First User",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower() or "conflict" in res2.json()["detail"].lower()


def test_login_success(client: TestClient):
    """Test logging in with valid credentials."""
    # Register user first
    reg_payload = {
        "email": "login_user@example.com",
        "password": "SecretPassword123!",
        "full_name": "Login User",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # Login
    login_payload = {
        "email": "login_user@example.com",
        "password": "SecretPassword123!",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data


def test_login_invalid_password_fails(client: TestClient):
    """Test login with wrong password returns 401."""
    reg_payload = {
        "email": "wrong_pass@example.com",
        "password": "CorrectPassword123!",
        "full_name": "Test User",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "wrong_pass@example.com",
        "password": "WrongPassword123!",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401


def test_get_current_user_me(client: TestClient, auth_headers: dict):
    """Test fetching /me endpoint with valid auth token."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test_user@example.com"


def test_get_current_user_unauthorized_fails(client: TestClient):
    """Test fetching /me without auth token returns 401 or 403."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)
