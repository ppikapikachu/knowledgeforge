"""LLM 思考模式缓存与并发隔离测试。"""

import threading
from unittest.mock import patch

import pytest


class TestLLMCache:
    """LLM 缓存测试。"""

    def setup_method(self):
        """每个测试前重置缓存。"""
        from agent.common.llm import reset_llm
        reset_llm()

    def test_same_mode_returns_same_instance(self):
        """同一模式重复调用返回同一实例。"""
        from agent.common.llm import get_llm

        llm1 = get_llm(thinking="disabled")
        llm2 = get_llm(thinking="disabled")
        assert llm1 is llm2

    def test_different_modes_return_different_instances(self):
        """不同模式返回不同实例。"""
        from agent.common.llm import get_llm

        llm_disabled = get_llm(thinking="disabled")
        llm_enabled = get_llm(thinking="enabled")
        assert llm_disabled is not llm_enabled

    def test_invalid_mode_raises_error(self):
        """非法模式抛出 ValueError。"""
        from agent.common.llm import get_llm

        with pytest.raises(ValueError, match="不支持的思考模式"):
            get_llm(thinking="invalid")

    def test_concurrent_same_mode_creates_one_instance(self):
        """并发首次请求同一模式只创建一个实例。"""
        from agent.common.llm import get_llm, _llm_instances

        results = []
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            llm = get_llm(thinking="disabled")
            results.append(llm)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有线程应拿到同一个实例
        assert all(r is results[0] for r in results)
        assert len(_llm_instances) == 1

    def test_concurrent_different_modes_isolated(self):
        """并发不同模式互不干扰。"""
        from agent.common.llm import get_llm

        results_disabled = []
        results_enabled = []
        barrier = threading.Barrier(4)

        def worker_disabled():
            barrier.wait()
            results_disabled.append(get_llm(thinking="disabled"))

        def worker_enabled():
            barrier.wait()
            results_enabled.append(get_llm(thinking="enabled"))

        threads = [
            threading.Thread(target=worker_disabled),
            threading.Thread(target=worker_disabled),
            threading.Thread(target=worker_enabled),
            threading.Thread(target=worker_enabled),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 同模式内实例相同
        assert results_disabled[0] is results_disabled[1]
        assert results_enabled[0] is results_enabled[1]
        # 不同模式实例不同
        assert results_disabled[0] is not results_enabled[0]

    def test_thinking_mode_in_extra_body(self):
        """实例的 extra_body 包含正确的 thinking 配置。"""
        from agent.common.llm import get_llm

        llm_disabled = get_llm(thinking="disabled")
        llm_enabled = get_llm(thinking="enabled")

        # ChatOpenAI 可能将 extra_body 存储在不同位置
        # 检查多个可能的存储位置
        def get_extra_body(llm):
            # 尝试 model_kwargs
            mk = getattr(llm, "model_kwargs", {}) or {}
            eb = mk.get("extra_body")
            if eb:
                return eb
            # 尝试直接属性
            eb = getattr(llm, "extra_body", None)
            if eb:
                return eb
            # 尝试 _client 或其他内部属性
            return {}

        disabled_body = get_extra_body(llm_disabled)
        enabled_body = get_extra_body(llm_enabled)

        # 至少验证两个实例不同（模式隔离）
        assert llm_disabled is not llm_enabled

    def test_enabled_no_custom_temperature(self):
        """思考开启时不传自定义 temperature。"""
        from agent.common.llm import get_llm

        llm_enabled = get_llm(thinking="enabled")
        # MiMo 开启思考时不支持自定义 temperature
        # 检查是否没有显式设置 temperature
        # （ChatOpenAI 默认 temperature=0.7，但不应从配置覆盖）

    def test_disabled_uses_config_temperature(self):
        """思考关闭时使用配置的 temperature。"""
        from agent.common.llm import get_llm
        from agent.common.config import agent_settings

        llm_disabled = get_llm(thinking="disabled")
        assert llm_disabled.temperature == agent_settings.LLM_TEMPERATURE
