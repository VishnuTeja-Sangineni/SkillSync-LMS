"""
Tests for role-based access control.

Verifies that:
- Students cannot access teacher or admin routes
- Teachers cannot access admin routes
- Admins can access everything
"""

from tests.conftest import create_test_users


def test_student_cannot_access_admin_users(client):
    """Students should get 403 on admin endpoints."""
    headers = create_test_users(client)
    resp = client.get("/api/v1/admin/users", headers=headers["student"])
    assert resp.status_code == 403


def test_teacher_cannot_access_admin_users(client):
    """Teachers should get 403 on admin endpoints."""
    headers = create_test_users(client)
    resp = client.get("/api/v1/admin/users", headers=headers["teacher"])
    assert resp.status_code == 403


def test_admin_can_access_admin_users(client):
    """Admins should get 200 on admin endpoints."""
    headers = create_test_users(client)
    resp = client.get("/api/v1/admin/users", headers=headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3  # admin, teacher, student


def test_admin_can_filter_users_by_role(client):
    """Admin can filter users by role."""
    headers = create_test_users(client)
    resp = client.get("/api/v1/admin/users?role=student", headers=headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["role"] == "student"


def test_admin_can_update_user_role(client):
    """Admin can change a user's role."""
    headers = create_test_users(client)

    # Get student user ID
    resp = client.get("/api/v1/admin/users?role=student", headers=headers["admin"])
    student_id = resp.json()[0]["id"]

    # Update role
    resp = client.patch(
        f"/api/v1/admin/users/{student_id}",
        json={"role": "teacher"},
        headers=headers["admin"],
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "teacher"


def test_admin_cannot_delete_self(client):
    """Admin cannot delete their own account."""
    headers = create_test_users(client)
    # Get admin's own user ID
    resp = client.get("/api/v1/auth/me", headers=headers["admin"])
    admin_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/admin/users/{admin_id}", headers=headers["admin"])
    assert resp.status_code == 400


def test_admin_can_delete_other_user(client):
    """Admin can delete another user."""
    headers = create_test_users(client)
    resp = client.get("/api/v1/admin/users?role=student", headers=headers["admin"])
    student_id = resp.json()[0]["id"]

    resp = client.delete(f"/api/v1/admin/users/{student_id}", headers=headers["admin"])
    assert resp.status_code == 204


def test_admin_stats(client):
    """Admin can view platform statistics."""
    headers = create_test_users(client)
    resp = client.get("/api/v1/admin/stats", headers=headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == 3
    assert data["total_students"] == 1
    assert data["total_teachers"] == 1
