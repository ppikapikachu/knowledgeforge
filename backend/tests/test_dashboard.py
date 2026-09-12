"""Dashboard tests."""

import pytest


class TestDashboard:
    """Test dashboard endpoint."""

    def test_dashboard_overview(self, client, auth_headers):
        """Test getting dashboard overview."""
        response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "knowledge_count" in data["data"]
        assert "question_count" in data["data"]
        assert "single_choice_count" in data["data"]
        assert "multiple_choice_count" in data["data"]
        assert "true_false_count" in data["data"]
        assert "short_answer_count" in data["data"]
        assert "import_task_count" in data["data"]

    def test_dashboard_with_data(self, client, auth_headers, sample_knowledge):
        """Test dashboard with existing data."""
        # Create questions of different types
        client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SINGLE_CHOICE",
                "content": "单选题",
                "answer": "A",
                "options": [
                    {"option_key": "A", "option_content": "A", "is_correct": 1, "sort_order": 0},
                    {"option_key": "B", "option_content": "B", "is_correct": 0, "sort_order": 1},
                ],
            },
        )
        client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={"question_type": "TRUE_FALSE", "content": "判断题", "answer": "TRUE"},
        )

        response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
        data = response.json()["data"]
        assert data["knowledge_count"] >= 1
        assert data["question_count"] >= 2
        assert data["single_choice_count"] >= 1
        assert data["true_false_count"] >= 1

    def test_dashboard_no_auth(self, client):
        """Test dashboard without authentication."""
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 401
