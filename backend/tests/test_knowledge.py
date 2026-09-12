"""Knowledge CRUD tests."""

import pytest


class TestKnowledgeCRUD:
    """Test knowledge CRUD operations."""

    def test_create_knowledge(self, client, auth_headers):
        """Test creating a knowledge point."""
        response = client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={
                "name": "Python装饰器",
                "summary": "装饰器是闭包的应用",
                "difficulty": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "Python装饰器"
        assert data["data"]["difficulty"] == 2

    def test_create_knowledge_minimal(self, client, auth_headers):
        """Test creating knowledge with minimal fields."""
        response = client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={"name": "最小知识点"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["name"] == "最小知识点"
        assert data["data"]["difficulty"] == 1

    def test_get_knowledge(self, client, auth_headers, sample_knowledge):
        """Test getting knowledge by ID."""
        kid = sample_knowledge["id"]
        response = client.get(f"/api/v1/knowledge/{kid}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == kid
        assert data["data"]["name"] == "Python装饰器"

    def test_get_knowledge_not_found(self, client, auth_headers):
        """Test getting non-existent knowledge."""
        response = client.get("/api/v1/knowledge/99999", headers=auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40401

    def test_update_knowledge(self, client, auth_headers, sample_knowledge):
        """Test updating a knowledge point."""
        kid = sample_knowledge["id"]
        response = client.put(
            f"/api/v1/knowledge/{kid}",
            headers=auth_headers,
            json={"name": "更新后的知识点", "difficulty": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["name"] == "更新后的知识点"
        assert data["data"]["difficulty"] == 3

    def test_delete_knowledge(self, client, auth_headers, sample_knowledge):
        """Test deleting (disabling) a knowledge point."""
        kid = sample_knowledge["id"]
        response = client.delete(f"/api/v1/knowledge/{kid}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == 0

    def test_list_knowledge(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test listing knowledge points."""
        response = client.get("/api/v1/knowledge", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 2
        assert len(data["data"]["items"]) == 2

    def test_list_knowledge_with_keyword(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test listing knowledge with keyword filter."""
        response = client.get(
            "/api/v1/knowledge?keyword=装饰器",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1

    def test_list_knowledge_with_difficulty(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test listing knowledge with difficulty filter."""
        response = client.get(
            "/api/v1/knowledge?difficulty=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 2

    def test_list_knowledge_pagination(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test knowledge list pagination."""
        response = client.get(
            "/api/v1/knowledge?page=1&page_size=1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 2
        assert len(data["data"]["items"]) == 1
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 1

    def test_create_knowledge_no_auth(self, client):
        """Test creating knowledge without authentication."""
        response = client.post(
            "/api/v1/knowledge",
            json={"name": "未认证"},
        )
        assert response.status_code == 401


class TestKnowledgeRelation:
    """Test knowledge relation operations."""

    def test_create_relation(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test creating a knowledge relation."""
        kid = sample_knowledge["id"]
        kid2 = sample_knowledge2["id"]
        response = client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={
                "target_knowledge_id": kid2,
                "relation_type": "prerequisite",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["source_knowledge_id"] == kid
        assert data["data"]["target_knowledge_id"] == kid2

    def test_create_relation_self(self, client, auth_headers, sample_knowledge):
        """Test that self-relation is prevented."""
        kid = sample_knowledge["id"]
        response = client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={
                "target_knowledge_id": kid,
                "relation_type": "related",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40001

    def test_create_relation_duplicate(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test that duplicate relations are prevented."""
        kid = sample_knowledge["id"]
        kid2 = sample_knowledge2["id"]

        # Create first relation
        client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={"target_knowledge_id": kid2, "relation_type": "prerequisite"},
        )

        # Try duplicate
        response = client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={"target_knowledge_id": kid2, "relation_type": "prerequisite"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40901

    def test_create_relation_invalid_type(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test creating relation with invalid type."""
        kid = sample_knowledge["id"]
        kid2 = sample_knowledge2["id"]
        response = client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={"target_knowledge_id": kid2, "relation_type": "invalid_type"},
        )
        assert response.status_code == 400

    def test_create_relation_target_not_found(self, client, auth_headers, sample_knowledge):
        """Test creating relation with non-existent target."""
        kid = sample_knowledge["id"]
        response = client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={"target_knowledge_id": 99999, "relation_type": "related"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 40401

    def test_get_relations(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test getting relations for a knowledge point."""
        kid = sample_knowledge["id"]
        kid2 = sample_knowledge2["id"]

        client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={"target_knowledge_id": kid2, "relation_type": "prerequisite"},
        )

        response = client.get(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

    def test_delete_relation(self, client, auth_headers, sample_knowledge, sample_knowledge2):
        """Test deleting a knowledge relation."""
        kid = sample_knowledge["id"]
        kid2 = sample_knowledge2["id"]

        # Create relation
        resp = client.post(
            f"/api/v1/knowledge/{kid}/relations",
            headers=auth_headers,
            json={"target_knowledge_id": kid2, "relation_type": "prerequisite"},
        )
        relation_id = resp.json()["data"]["id"]

        # Delete relation
        response = client.delete(
            f"/api/v1/knowledge/{kid}/relations/{relation_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
