"""Import task tests."""

import io

import pytest


class TestImportTask:
    """Test import task operations."""

    def test_upload_txt_file(self, client, auth_headers):
        """Test uploading a TXT file."""
        file_content = b"Test file content for import"
        response = client.post(
            "/api/v1/import-tasks",
            headers=auth_headers,
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "task_id" in data["data"]

    def test_upload_md_file(self, client, auth_headers):
        """Test uploading a MD file."""
        file_content = b"# Test Markdown"
        response = client.post(
            "/api/v1/import-tasks",
            headers=auth_headers,
            files={"file": ("test.md", io.BytesIO(file_content), "text/markdown")},
        )
        assert response.status_code == 200

    def test_upload_invalid_extension(self, client, auth_headers):
        """Test uploading file with invalid extension."""
        file_content = b"MZ..."
        response = client.post(
            "/api/v1/import-tasks",
            headers=auth_headers,
            files={"file": ("test.exe", io.BytesIO(file_content), "application/octet-stream")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40001

    def test_get_import_task(self, client, auth_headers):
        """Test getting import task by ID."""
        # Create task first
        file_content = b"Test content"
        create_resp = client.post(
            "/api/v1/import-tasks",
            headers=auth_headers,
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        task_id = create_resp.json()["data"]["task_id"]

        response = client.get(
            f"/api/v1/import-tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == task_id
        assert data["data"]["status"] == "PENDING"

    def test_get_import_task_not_found(self, client, auth_headers):
        """Test getting non-existent import task."""
        response = client.get("/api/v1/import-tasks/99999", headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["code"] == 40401

    def test_list_import_tasks(self, client, auth_headers):
        """Test listing import tasks."""
        # Create a few tasks
        for i in range(3):
            client.post(
                "/api/v1/import-tasks",
                headers=auth_headers,
                files={"file": (f"test{i}.txt", io.BytesIO(b"content"), "text/plain")},
            )

        response = client.get("/api/v1/import-tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 3

    def test_simulate_task_progress(self, client, auth_headers):
        """Test simulating task progress."""
        # Create task
        create_resp = client.post(
            "/api/v1/import-tasks",
            headers=auth_headers,
            files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        task_id = create_resp.json()["data"]["task_id"]

        # Simulate progress
        response = client.post(
            f"/api/v1/import-tasks/{task_id}/simulate",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "RUNNING"
        assert data["data"]["progress"] > 0

    def test_upload_no_auth(self, client):
        """Test uploading without authentication."""
        response = client.post(
            "/api/v1/import-tasks",
            files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        assert response.status_code == 401
