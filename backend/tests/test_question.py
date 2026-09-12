"""Question CRUD tests."""

import pytest


class TestQuestionCRUD:
    """Test question CRUD operations."""

    def test_create_single_choice(self, client, auth_headers, sample_knowledge):
        """Test creating a single choice question."""
        kid = sample_knowledge["id"]
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SINGLE_CHOICE",
                "content": "Python中哪个关键字定义装饰器？",
                "answer": "A",
                "difficulty": 2,
                "options": [
                    {"option_key": "A", "option_content": "@", "is_correct": 1, "sort_order": 0},
                    {"option_key": "B", "option_content": "#", "is_correct": 0, "sort_order": 1},
                    {"option_key": "C", "option_content": "$", "is_correct": 0, "sort_order": 2},
                    {"option_key": "D", "option_content": "&", "is_correct": 0, "sort_order": 3},
                ],
                "knowledge_ids": [kid],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["question_type"] == "SINGLE_CHOICE"
        assert len(data["data"]["options"]) == 4
        assert len(data["data"]["knowledge_ids"]) == 1

    def test_create_multiple_choice(self, client, auth_headers):
        """Test creating a multiple choice question."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "MULTIPLE_CHOICE",
                "content": "哪些是Python内置装饰器？",
                "answer": "A,C",
                "difficulty": 3,
                "options": [
                    {"option_key": "A", "option_content": "@staticmethod", "is_correct": 1, "sort_order": 0},
                    {"option_key": "B", "option_content": "@inject", "is_correct": 0, "sort_order": 1},
                    {"option_key": "C", "option_content": "@classmethod", "is_correct": 1, "sort_order": 2},
                    {"option_key": "D", "option_content": "@override", "is_correct": 0, "sort_order": 3},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["question_type"] == "MULTIPLE_CHOICE"
        correct = sum(1 for o in data["data"]["options"] if o["is_correct"] == 1)
        assert correct == 2

    def test_create_true_false(self, client, auth_headers):
        """Test creating a true/false question."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "装饰器只能用于函数",
                "answer": "FALSE",
                "difficulty": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["question_type"] == "TRUE_FALSE"
        assert data["data"]["options"] == []

    def test_create_short_answer(self, client, auth_headers):
        """Test creating a short answer question."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SHORT_ANSWER",
                "content": "解释装饰器原理",
                "answer": "高阶函数接受函数作为参数",
                "difficulty": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["question_type"] == "SHORT_ANSWER"

    def test_get_question(self, client, auth_headers):
        """Test getting question by ID."""
        # Create first
        create_resp = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "测试题目",
                "answer": "TRUE",
            },
        )
        qid = create_resp.json()["data"]["id"]

        response = client.get(f"/api/v1/questions/{qid}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == qid

    def test_get_question_not_found(self, client, auth_headers):
        """Test getting non-existent question."""
        response = client.get("/api/v1/questions/99999", headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["code"] == 40401

    def test_update_question(self, client, auth_headers):
        """Test updating a question."""
        create_resp = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "原始内容",
                "answer": "TRUE",
                "difficulty": 1,
            },
        )
        qid = create_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/questions/{qid}",
            headers=auth_headers,
            json={"content": "更新后的内容", "difficulty": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["content"] == "更新后的内容"
        assert data["data"]["difficulty"] == 3

    def test_delete_question(self, client, auth_headers):
        """Test deleting (disabling) a question."""
        create_resp = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "待删除",
                "answer": "TRUE",
            },
        )
        qid = create_resp.json()["data"]["id"]

        response = client.delete(f"/api/v1/questions/{qid}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "DISABLED"

    def test_list_questions(self, client, auth_headers):
        """Test listing questions."""
        # Create a few questions
        for i in range(3):
            client.post(
                "/api/v1/questions",
                headers=auth_headers,
                json={
                    "question_type": "TRUE_FALSE",
                    "content": f"题目{i}",
                    "answer": "TRUE",
                },
            )

        response = client.get("/api/v1/questions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 3

    def test_list_questions_filter_type(self, client, auth_headers):
        """Test listing questions with type filter."""
        client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={"question_type": "TRUE_FALSE", "content": "判断题", "answer": "TRUE"},
        )
        client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SHORT_ANSWER",
                "content": "简答题",
                "answer": "答案",
            },
        )

        response = client.get(
            "/api/v1/questions?question_type=TRUE_FALSE",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1


class TestQuestionValidation:
    """Test question type validation rules."""

    def test_single_choice_needs_two_options(self, client, auth_headers):
        """Test that single choice needs at least 2 options."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SINGLE_CHOICE",
                "content": "题目",
                "answer": "A",
                "options": [
                    {"option_key": "A", "option_content": "唯一选项", "is_correct": 1, "sort_order": 0},
                ],
            },
        )
        # Pydantic validation returns 422
        assert response.status_code in (400, 422)

    def test_single_choice_one_correct(self, client, auth_headers):
        """Test that single choice must have exactly 1 correct answer."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SINGLE_CHOICE",
                "content": "题目",
                "answer": "A,B",
                "options": [
                    {"option_key": "A", "option_content": "A", "is_correct": 1, "sort_order": 0},
                    {"option_key": "B", "option_content": "B", "is_correct": 1, "sort_order": 1},
                ],
            },
        )
        assert response.status_code in (400, 422)

    def test_multiple_choice_needs_correct(self, client, auth_headers):
        """Test that multiple choice needs at least 1 correct answer."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "MULTIPLE_CHOICE",
                "content": "题目",
                "answer": "",
                "options": [
                    {"option_key": "A", "option_content": "A", "is_correct": 0, "sort_order": 0},
                    {"option_key": "B", "option_content": "B", "is_correct": 0, "sort_order": 1},
                ],
            },
        )
        assert response.status_code in (400, 422)

    def test_true_false_no_options(self, client, auth_headers):
        """Test that true/false questions should not have options."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "题目",
                "answer": "TRUE",
                "options": [
                    {"option_key": "A", "option_content": "选项", "is_correct": 1, "sort_order": 0},
                ],
            },
        )
        assert response.status_code in (400, 422)

    def test_true_false_invalid_answer(self, client, auth_headers):
        """Test that true/false answer must be TRUE or FALSE."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "题目",
                "answer": "YES",
            },
        )
        assert response.status_code in (400, 422)

    def test_short_answer_no_options(self, client, auth_headers):
        """Test that short answer questions should not have options."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "SHORT_ANSWER",
                "content": "题目",
                "answer": "答案",
                "options": [
                    {"option_key": "A", "option_content": "选项", "is_correct": 1, "sort_order": 0},
                ],
            },
        )
        assert response.status_code in (400, 422)

    def test_invalid_question_type(self, client, auth_headers):
        """Test that invalid question type is rejected."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "INVALID_TYPE",
                "content": "题目",
                "answer": "答案",
            },
        )
        assert response.status_code == 400

    def test_question_with_nonexistent_knowledge(self, client, auth_headers):
        """Test creating question with non-existent knowledge ID."""
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers,
            json={
                "question_type": "TRUE_FALSE",
                "content": "题目",
                "answer": "TRUE",
                "knowledge_ids": [99999],
            },
        )
        assert response.status_code == 400
        assert response.json()["code"] == 40401
