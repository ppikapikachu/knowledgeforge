"""Authentication tests."""

import pytest


class TestLogin:
    """Test login endpoint."""

    def test_login_success(self, client, admin_user):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testadmin", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"

    def test_login_wrong_password(self, client, admin_user):
        """Test login with wrong password."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testadmin", "password": "wrongpassword"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40101

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "testpass123"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40101

    def test_login_disabled_user(self, client, db, admin_user):
        """Test login with disabled user."""
        admin_user.status = 0
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testadmin", "password": "testpass123"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40101

    def test_login_empty_username(self, client):
        """Test login with empty username."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": "testpass123"},
        )
        assert response.status_code == 422

    def test_login_missing_fields(self, client):
        """Test login with missing fields."""
        response = client.post(
            "/api/v1/auth/login",
            json={},
        )
        assert response.status_code == 422


class TestGetMe:
    """Test get current admin info endpoint."""

    def test_get_me_success(self, client, auth_headers):
        """Test getting current admin info."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["username"] == "testadmin"

    def test_get_me_no_token(self, client):
        """Test getting admin info without token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client):
        """Test getting admin info with invalid token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40101
