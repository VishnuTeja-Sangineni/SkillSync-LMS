"""
Tests for frontend static file serving and SPA shell structure.
"""

def test_frontend_index_serving(client):
    """The root route / should serve index.html with SPA views and demo accounts."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SkillSync LMS" in resp.text
    # Verify views exist
    assert 'data-view="student-dashboard"' in resp.text
    assert 'data-view="teacher-dashboard"' in resp.text
    assert 'data-view="admin-dashboard"' in resp.text
    assert 'data-view="quiz"' in resp.text
    assert 'data-view="lesson"' in resp.text
    assert 'data-view="course"' in resp.text
    # Verify demo buttons exist
    assert 'data-demo-user="student"' in resp.text
    assert 'data-demo-user="teacher"' in resp.text
    assert 'data-demo-user="admin"' in resp.text


def test_frontend_assets_served(client):
    """Static assets (CSS, JS modules) should be reachable at root static mount."""
    assets = [
        "/css/style.css",
        "/js/config.js",
        "/js/api.js",
        "/js/utils.js",
        "/js/charts.js",
        "/js/router.js",
        "/js/auth.js",
        "/js/app.js",
    ]
    for asset in assets:
        resp = client.get(asset)
        assert resp.status_code == 200, f"Asset {asset} failed to load: status {resp.status_code}"
        assert len(resp.text) > 0
