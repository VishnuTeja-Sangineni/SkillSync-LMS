"""
Tests for auth endpoints: register, login, and /me.
"""

from tests.conftest import register_user, get_auth_header


def test_register_success(client):
    """A new user can register and receives a token."""
    resp = register_user(client, "Alice", "alice@test.com", "Alice@123", "student")
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["name"] == "Alice"
    assert data["user"]["email"] == "alice@test.com"
    assert data["user"]["role"] == "student"


def test_register_duplicate_email(client):
    """Registering with an existing email returns 409."""
    register_user(client, "Alice", "alice@test.com", "Alice@123")
    resp = register_user(client, "Alice2", "alice@test.com", "Alice@123")
    assert resp.status_code == 409


def test_register_invalid_role(client):
    """Registering with an invalid role returns 422."""
    resp = client.post("/api/v1/auth/register", json={
        "name": "Bad", "email": "bad@test.com", "password": "Bad@123", "role": "superuser"
    })
    assert resp.status_code == 422


def test_register_short_password(client):
    """Password must be at least 6 characters."""
    resp = client.post("/api/v1/auth/register", json={
        "name": "Short", "email": "short@test.com", "password": "123", "role": "student"
    })
    assert resp.status_code == 422


def test_login_success(client):
    """A registered user can login and receive a token."""
    register_user(client, "Bob", "bob@test.com", "Bob@1234")
    resp = client.post("/api/v1/auth/login", json={
        "email": "bob@test.com", "password": "Bob@1234"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "bob@test.com"


def test_login_wrong_password(client):
    """Login with wrong password returns 401."""
    register_user(client, "Carol", "carol@test.com", "Carol@123")
    resp = client.post("/api/v1/auth/login", json={
        "email": "carol@test.com", "password": "WrongPassword"
    })
    assert resp.status_code == 401


def test_login_nonexistent_email(client):
    """Login with unregistered email returns 401."""
    resp = client.post("/api/v1/auth/login", json={
        "email": "nobody@test.com", "password": "Whatever"
    })
    assert resp.status_code == 401


def test_me_authenticated(client):
    """Authenticated user can access /me."""
    register_user(client, "Dave", "dave@test.com", "Dave@123")
    headers = get_auth_header(client, "dave@test.com", "Dave@123")
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "dave@test.com"


def test_me_unauthenticated(client):
    """Unauthenticated request to /me returns 401."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_invalid_token(client):
    """Invalid token returns 401."""
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
