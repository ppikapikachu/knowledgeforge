"""题库-知识库映射 API 测试。"""

import pytest


class TestKnowledgeBaseMapping:
    """题库-知识库映射 CRUD 测试。"""

    def _get_kb_ids(self, client, auth_headers):
        """获取知识库 ID 列表。"""
        resp = client.get("/api/v1/knowledge-bases", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        return [item["id"] for item in data["items"]]

    def _get_question_bank_id(self, client, auth_headers):
        """获取实际题库 ID。"""
        resp = client.get("/api/v1/question-banks", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()["data"]
            items = data.get("items", [])
            if items:
                return items[0]["id"]
        return 1

    def test_put_mapping_success(self, client, auth_headers):
        """首次设置多个知识库成功。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        assert len(kb_ids) >= 2
        target_ids = kb_ids[:2]
        bank_id = self._get_question_bank_id(client, auth_headers)

        resp = client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": target_ids},
        )
        assert resp.status_code == 200, f"PUT failed: {resp.json()}"
        data = resp.json()["data"]
        assert data["question_bank_id"] == bank_id
        assert sorted(data["knowledge_base_ids"]) == sorted(target_ids)

        # GET 验证读回
        resp2 = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert sorted(data2["knowledge_base_ids"]) == sorted(target_ids)

    def test_put_mapping_replace(self, client, auth_headers):
        """再次 PUT 不同 ID 集合，旧关联被完整替换。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        assert len(kb_ids) >= 3
        bank_id = self._get_question_bank_id(client, auth_headers)

        # 先设 kb_ids[0], kb_ids[1]
        client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [kb_ids[0], kb_ids[1]]},
        )

        # 替换为 kb_ids[2]
        resp = client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [kb_ids[2]]},
        )
        assert resp.status_code == 200, f"PUT failed: {resp.json()}"

        resp2 = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        data2 = resp2.json()["data"]
        assert sorted(data2["knowledge_base_ids"]) == [kb_ids[2]]

    def test_put_mapping_idempotent(self, client, auth_headers):
        """PUT 相同集合多次，结果不重复。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        target_ids = kb_ids[:2]
        bank_id = self._get_question_bank_id(client, auth_headers)

        for _ in range(3):
            resp = client.put(
                f"/api/v1/question-banks/{bank_id}/knowledge-bases",
                headers=auth_headers,
                json={"knowledge_base_ids": target_ids},
            )
            assert resp.status_code == 200

        resp2 = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        data2 = resp2.json()["data"]
        assert sorted(data2["knowledge_base_ids"]) == sorted(target_ids)
        assert len(data2["items"]) == len(target_ids)

    def test_put_mapping_empty_array(self, client, auth_headers):
        """PUT 空数组，正确清空关系。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        bank_id = self._get_question_bank_id(client, auth_headers)
        # 先设
        client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": kb_ids[:2]},
        )

        # 清空
        resp = client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": []},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["knowledge_base_ids"] == []

        # GET 确认清空
        resp2 = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        data2 = resp2.json()["data"]
        assert data2["knowledge_base_ids"] == []

    def test_put_mapping_nonexistent_bank(self, client, auth_headers):
        """题库 ID 不存在，返回明确 404/业务错误。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        resp = client.put(
            "/api/v1/question-banks/99999/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": kb_ids[:1]},
        )
        assert resp.status_code in (400, 404)

    def test_put_mapping_nonexistent_kb(self, client, auth_headers):
        """知识库 ID 不存在，返回明确 400/业务错误。"""
        bank_id = self._get_question_bank_id(client, auth_headers)
        resp = client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [99999]},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["code"] == 40001

    def test_put_mapping_partial_invalid_rollback(self, client, auth_headers):
        """ID 集合中一个合法、一个非法，整个事务不应部分提交。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        bank_id = self._get_question_bank_id(client, auth_headers)
        # 先设一个有效映射
        client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [kb_ids[0]]},
        )

        # 提交混合有效+无效 ID
        resp = client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [kb_ids[1], 99999]},
        )
        assert resp.status_code == 400

        # 验证原映射未被修改
        resp2 = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        data2 = resp2.json()["data"]
        assert data2["knowledge_base_ids"] == [kb_ids[0]]

    def test_put_mapping_duplicate_ids(self, client, auth_headers):
        """重复 ID 的处理符合文档约定（去重）。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        bank_id = self._get_question_bank_id(client, auth_headers)
        target = kb_ids[0]

        resp = client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [target, target, target]},
        )
        assert resp.status_code == 200, f"PUT failed: {resp.json()}"

        resp2 = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        data2 = resp2.json()["data"]
        assert data2["knowledge_base_ids"] == [target]
        assert len(data2["items"]) == 1

    def test_get_mapping_after_put(self, client, auth_headers):
        """GET 能读回 PUT 保存的真实关系。"""
        kb_ids = self._get_kb_ids(client, auth_headers)
        bank_id = self._get_question_bank_id(client, auth_headers)
        target_ids = kb_ids[:2]

        client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": target_ids},
        )

        resp = client.get(f"/api/v1/question-banks/{bank_id}/knowledge-bases", headers=auth_headers)
        data = resp.json()["data"]
        assert sorted(data["knowledge_base_ids"]) == sorted(target_ids)
        assert len(data["items"]) == len(target_ids)
        for item in data["items"]:
            assert "id" in item
            assert "name" in item
            assert "knowledge_count" in item

    def test_get_mapping_nonexistent_bank(self, client, auth_headers):
        """查询不存在的题库映射，返回 404。"""
        resp = client.get("/api/v1/question-banks/99999/knowledge-bases", headers=auth_headers)
        assert resp.status_code in (400, 404)

    def test_put_mapping_no_auth(self, client):
        """无 Token 无法操作映射。"""
        resp = client.put(
            "/api/v1/question-banks/1/knowledge-bases",
            json={"knowledge_base_ids": [1]},
        )
        assert resp.status_code == 401

    def test_get_mapping_no_auth(self, client):
        """无 Token 无法查询映射。"""
        resp = client.get("/api/v1/question-banks/1/knowledge-bases")
        assert resp.status_code == 401
