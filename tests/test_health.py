"""
Tests for /api/v1/health and /api/v1/ready endpoints.
"""


def test_health(client):
    """Health endpoint should always return 200 with status 'healthy'."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "skillsync-lms"


def test_ready(client):
    """Ready endpoint should return 200 when database is connected."""
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_request_id_header(client):
    """Every response should include an X-Request-ID header."""
    resp = client.get("/api/v1/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0
