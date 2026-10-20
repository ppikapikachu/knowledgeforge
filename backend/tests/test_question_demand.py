"""出题策略、智能分配预览、auto 任务创建 API 测试。"""

import pytest


class TestPolicyManagement:
    """策略管理测试。"""

    def test_get_effective_policy_global(self, client, auth_headers):
        """无题库覆盖时返回全局策略。"""
        resp = client.get("/api/v1/question-generation/policies/effective", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["source"] == "global_default"
        assert data["policy"]["stock_weight"] == 50
        assert data["policy"]["usage_weight"] == 30
        assert data["policy"]["importance_weight"] == 20
        assert data["policy"]["is_enabled"] is True

    def test_save_global_policy(self, client, auth_headers):
        """保存全局策略成功。"""
        resp = client.put(
            "/api/v1/question-generation/policies/global",
            headers=auth_headers,
            json={
                "stock_weight": 60, "usage_weight": 20, "importance_weight": 20,
                "target_stock": 30, "usage_window_days": 30,
                "recent_answers_per_question_target": 5, "usage_extra_ratio": 0.5,
                "max_per_knowledge_per_task": 8, "min_demand_score": 0.1,
                "is_enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["stock_weight"] == 60
        assert data["version"] >= 1

    def test_save_question_bank_policy(self, client, auth_headers):
        """保存题库级策略覆盖。"""
        bank_id = self._get_bank_id(client, auth_headers)
        resp = client.put(
            f"/api/v1/question-generation/policies/question-banks/{bank_id}",
            headers=auth_headers,
            json={
                "stock_weight": 40, "usage_weight": 40, "importance_weight": 20,
                "target_stock": 15, "usage_window_days": 14,
                "recent_answers_per_question_target": 3, "usage_extra_ratio": 0.3,
                "max_per_knowledge_per_task": 5, "min_demand_score": 0.2,
                "is_enabled": True,
            },
        )
        assert resp.status_code == 200

        # 读取生效策略，应返回题库级
        resp2 = client.get(
            "/api/v1/question-generation/policies/effective",
            params={"question_bank_id": bank_id},
            headers=auth_headers,
        )
        data2 = resp2.json()["data"]
        assert data2["source"] == "question_bank_override"
        assert data2["policy"]["stock_weight"] == 40

    def test_delete_question_bank_policy(self, client, auth_headers):
        """删除题库级策略后回退全局策略。"""
        bank_id = self._get_bank_id(client, auth_headers)
        # 先设题库级
        client.put(
            f"/api/v1/question-generation/policies/question-banks/{bank_id}",
            headers=auth_headers,
            json={
                "stock_weight": 40, "usage_weight": 40, "importance_weight": 20,
                "target_stock": 15, "usage_window_days": 14,
                "recent_answers_per_question_target": 3, "usage_extra_ratio": 0.3,
                "max_per_knowledge_per_task": 5, "min_demand_score": 0.2,
                "is_enabled": True,
            },
        )

        # 删除
        resp = client.delete(
            f"/api/v1/question-generation/policies/question-banks/{bank_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # 验证回退
        resp2 = client.get(
            "/api/v1/question-generation/policies/effective",
            params={"question_bank_id": bank_id},
            headers=auth_headers,
        )
        data2 = resp2.json()["data"]
        assert data2["source"] == "global_default"

    def test_policy_weights_invalid_sum(self, client, auth_headers):
        """权重之和不等于 100 返回 400。"""
        resp = client.put(
            "/api/v1/question-generation/policies/global",
            headers=auth_headers,
            json={
                "stock_weight": 50, "usage_weight": 30, "importance_weight": 30,
                "target_stock": 20, "usage_window_days": 30,
                "recent_answers_per_question_target": 3, "usage_extra_ratio": 0.5,
                "max_per_knowledge_per_task": 10, "min_demand_score": 0.15,
                "is_enabled": True,
            },
        )
        assert resp.status_code == 400

    def test_policy_field_bounds(self, client, auth_headers):
        """字段越界返回 422。"""
        resp = client.put(
            "/api/v1/question-generation/policies/global",
            headers=auth_headers,
            json={
                "stock_weight": 50, "usage_weight": 30, "importance_weight": 20,
                "target_stock": 1000,  # 超出 1~500
                "usage_window_days": 30,
                "recent_answers_per_question_target": 3, "usage_extra_ratio": 0.5,
                "max_per_knowledge_per_task": 10, "min_demand_score": 0.15,
                "is_enabled": True,
            },
        )
        assert resp.status_code == 422

    def _get_bank_id(self, client, auth_headers):
        resp = client.get("/api/v1/question-banks", headers=auth_headers)
        if resp.status_code == 200:
            items = resp.json()["data"].get("items", [])
            if items:
                return items[0]["id"]
        return 1


class TestAllocationPreview:
    """智能分配预览测试。"""

    def _setup_mapping(self, client, auth_headers):
        """设置题库-知识库映射，返回 kb_id。"""
        kb_resp = client.get("/api/v1/knowledge-bases", headers=auth_headers)
        kb_ids = [item["id"] for item in kb_resp.json()["data"]["items"]]

        bank_resp = client.get("/api/v1/question-banks", headers=auth_headers)
        bank_items = bank_resp.json()["data"].get("items", [])
        bank_id = bank_items[0]["id"] if bank_items else 1

        client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": kb_ids[:1]},
        )
        return kb_ids[0], bank_id

    def test_preview_no_mapping_warning(self, client, auth_headers):
        """题库未关联知识库时，返回明确 warning。"""
        bank_resp = client.get("/api/v1/question-banks", headers=auth_headers)
        bank_items = bank_resp.json()["data"].get("items", [])
        bank_id = bank_items[0]["id"] if bank_items else 1

        resp = client.post(
            "/api/v1/question-generation/allocations/preview",
            headers=auth_headers,
            json={"question_bank_id": bank_id, "question_type": "SINGLE_CHOICE", "difficulty": 2, "count": 3},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["allocatable_count"] == 0
        assert data["unallocated_count"] == 3
        assert data["is_fully_allocatable"] is False
        # 必须有明确的 warning
        assert len(data["warnings"]) > 0
        assert any("SCOPE_NOT_CONFIGURED" in w or "未关联" in w for w in data["warnings"])

    def test_preview_with_knowledge(self, client, auth_headers):
        """配置映射且有知识点时，返回分配结果。"""
        kb_id, bank_id = self._setup_mapping(client, auth_headers)

        # 创建知识点
        client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={
                "name": "测试知识点A",
                "summary": "测试",
                "difficulty": 2,
                "knowledge_base_id": kb_id,
                "status": 1,
            },
        )

        resp = client.post(
            "/api/v1/question-generation/allocations/preview",
            headers=auth_headers,
            json={"question_bank_id": bank_id, "question_type": "SINGLE_CHOICE", "difficulty": 2, "count": 3},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # allocatable + unallocated = requested
        assert data["allocatable_count"] + data["unallocated_count"] == 3

    def test_preview_count_consistency(self, client, auth_headers):
        """allocated + unallocated == requested。"""
        kb_id, bank_id = self._setup_mapping(client, auth_headers)

        client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={"name": "测试知识点B", "difficulty": 2, "knowledge_base_id": kb_id, "status": 1},
        )

        resp = client.post(
            "/api/v1/question-generation/allocations/preview",
            headers=auth_headers,
            json={"question_bank_id": bank_id, "question_type": "SINGLE_CHOICE", "difficulty": 2, "count": 5},
        )
        data = resp.json()["data"]
        assert data["requested_count"] == 5
        assert data["allocatable_count"] + data["unallocated_count"] == 5

    def test_preview_no_side_effects(self, client, auth_headers):
        """预览不创建任务、不写入题目。"""
        kb_id, bank_id = self._setup_mapping(client, auth_headers)

        resp = client.post(
            "/api/v1/question-generation/allocations/preview",
            headers=auth_headers,
            json={"question_bank_id": bank_id, "question_type": "SINGLE_CHOICE", "difficulty": 2, "count": 3},
        )
        assert resp.status_code == 200

        # 确认任务列表为空
        tasks_resp = client.get("/api/v1/question-generation/tasks", headers=auth_headers)
        tasks_data = tasks_resp.json()["data"]
        assert tasks_data["total"] == 0


class TestAutoTaskCreate:
    """auto 模式任务创建测试。"""

    def _setup_mapping_and_knowledge(self, client, auth_headers):
        """设置映射和知识点。"""
        kb_resp = client.get("/api/v1/knowledge-bases", headers=auth_headers)
        kb_id = kb_resp.json()["data"]["items"][0]["id"]

        bank_resp = client.get("/api/v1/question-banks", headers=auth_headers)
        bank_items = bank_resp.json()["data"].get("items", [])
        bank_id = bank_items[0]["id"] if bank_items else 1

        client.put(
            f"/api/v1/question-banks/{bank_id}/knowledge-bases",
            headers=auth_headers,
            json={"knowledge_base_ids": [kb_id]},
        )
        client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={"name": "auto测试知识点", "difficulty": 2, "knowledge_base_id": kb_id, "status": 1},
        )
        return kb_id, bank_id

    def test_auto_task_create(self, client, auth_headers):
        """auto 模式创建任务成功。"""
        kb_id, bank_id = self._setup_mapping_and_knowledge(client, auth_headers)

        resp = client.post(
            "/api/v1/question-generation/tasks",
            headers=auth_headers,
            json={
                "allocation_mode": "auto",
                "question_bank_id": bank_id,
                "question_type": "SINGLE_CHOICE",
                "difficulty": 2,
                "count": 2,
            },
        )
        assert resp.status_code == 200, f"Failed: {resp.json()}"
        data = resp.json()["data"]
        assert data["allocation_mode"] == "auto"
        assert data["task_id"] > 0
        assert data["allocated_count"] + data["unallocated_count"] == 2

    def test_auto_task_no_candidates(self, client, auth_headers):
        """无候选知识点时创建 auto 任务返回明确错误。"""
        bank_resp = client.get("/api/v1/question-banks", headers=auth_headers)
        bank_items = bank_resp.json()["data"].get("items", [])
        bank_id = bank_items[0]["id"] if bank_items else 1

        resp = client.post(
            "/api/v1/question-generation/tasks",
            headers=auth_headers,
            json={
                "allocation_mode": "auto",
                "question_bank_id": bank_id,
                "question_type": "SINGLE_CHOICE",
                "difficulty": 2,
                "count": 3,
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["code"] == 40001

    def test_auto_task_allow_partial(self, client, auth_headers):
        """allow_partial=true 时允许部分分配。"""
        kb_id, bank_id = self._setup_mapping_and_knowledge(client, auth_headers)

        resp = client.post(
            "/api/v1/question-generation/tasks",
            headers=auth_headers,
            json={
                "allocation_mode": "auto",
                "question_bank_id": bank_id,
                "question_type": "SINGLE_CHOICE",
                "difficulty": 2,
                "count": 50,
                "allow_partial": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["allocated_count"] < 50  # 肯定无法全部分配

    def test_auto_task_insufficient_no_partial(self, client, auth_headers):
        """allow_partial=false 且不足时返回 ALLOCATION_INSUFFICIENT。"""
        kb_id, bank_id = self._setup_mapping_and_knowledge(client, auth_headers)

        resp = client.post(
            "/api/v1/question-generation/tasks",
            headers=auth_headers,
            json={
                "allocation_mode": "auto",
                "question_bank_id": bank_id,
                "question_type": "SINGLE_CHOICE",
                "difficulty": 2,
                "count": 50,
                "allow_partial": False,
            },
        )
        assert resp.status_code == 400

    def test_task_detail_has_allocation_plan(self, client, auth_headers):
        """任务详情返回创建时的分配快照。"""
        kb_id, bank_id = self._setup_mapping_and_knowledge(client, auth_headers)

        create_resp = client.post(
            "/api/v1/question-generation/tasks",
            headers=auth_headers,
            json={
                "allocation_mode": "auto",
                "question_bank_id": bank_id,
                "question_type": "SINGLE_CHOICE",
                "difficulty": 2,
                "count": 2,
                "allow_partial": True,
            },
        )
        task_id = create_resp.json()["data"]["task_id"]

        detail_resp = client.get(f"/api/v1/question-generation/tasks/{task_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()["data"]
        assert detail["allocation_mode"] == "auto"
        assert detail["allocation_plan"] is not None
        assert "items" in detail["allocation_plan"]
        assert detail["requested_count"] == 2

    def test_manual_task_create(self, client, auth_headers):
        """manual 模式创建任务成功。"""
        kb_resp = client.get("/api/v1/knowledge-bases", headers=auth_headers)
        kb_id = kb_resp.json()["data"]["items"][0]["id"]

        bank_resp = client.get("/api/v1/question-banks", headers=auth_headers)
        bank_items = bank_resp.json()["data"].get("items", [])
        bank_id = bank_items[0]["id"] if bank_items else 1

        # 创建知识点
        k_resp = client.post(
            "/api/v1/knowledge",
            headers=auth_headers,
            json={"name": "manual测试知识点", "difficulty": 2, "knowledge_base_id": kb_id, "status": 1},
        )
        kid = k_resp.json()["data"]["id"]

        resp = client.post(
            "/api/v1/question-generation/tasks",
            headers=auth_headers,
            json={
                "allocation_mode": "manual",
                "knowledge_id": kid,
                "question_bank_id": bank_id,
                "question_type": "SINGLE_CHOICE",
                "difficulty": 2,
                "count": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["allocation_mode"] == "manual"
        assert data["allocated_count"] == 2
        assert data["unallocated_count"] == 0


class TestImportanceAPI:
    """知识点重要程度 API 测试。"""

    def test_update_importance(self, client, auth_headers, sample_knowledge):
        """手动设置重要程度，source 变为 manual。"""
        kid = sample_knowledge["id"]
        resp = client.patch(
            f"/api/v1/knowledge/{kid}/importance",
            headers=auth_headers,
            json={"importance_level": "core"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["importance_level"] == "core"
        assert data["importance_source"] == "manual"

    def test_update_importance_invalid_enum(self, client, auth_headers, sample_knowledge):
        """非法枚举返回 400。"""
        kid = sample_knowledge["id"]
        resp = client.patch(
            f"/api/v1/knowledge/{kid}/importance",
            headers=auth_headers,
            json={"importance_level": "super_critical"},
        )
        assert resp.status_code == 400

    def test_knowledge_response_has_importance(self, client, auth_headers, sample_knowledge):
        """Knowledge 列表/详情返回 importance_level 和 importance_source。"""
        kid = sample_knowledge["id"]
        resp = client.get(f"/api/v1/knowledge/{kid}", headers=auth_headers)
        data = resp.json()["data"]
        assert "importance_level" in data
        assert "importance_source" in data
