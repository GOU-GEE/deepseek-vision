"""提供商测试：OpenAI 兼容实现、错误包装、多提供商切换。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest
from openai import AuthenticationError

from deepseek_vision_mcp.providers import build_provider
from deepseek_vision_mcp.providers.base import VisionProviderError
from deepseek_vision_mcp.providers.openai_compatible import (
    OpenAICompatibleProvider,
)

DATA_URI = "data:image/jpeg;base64,AAAA"


class FakeAPIError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def _mock_response(text="这是一只猫", model="mock-vl", usage=None):
    if usage is None:
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model=model,
        usage=usage,
    )


class TestOpenAICompatibleProvider:
    def test_analyze_success_builds_correct_request(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = _mock_response()
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ) as m_openai:
            provider = OpenAICompatibleProvider(
                api_key="k", model="glm-4.6v-flash", base_url="https://x/v4"
            )
            result = provider.analyze(DATA_URI, "请描述这张图")

        # 客户端按预期参数构造
        m_openai.assert_called_once_with(
            api_key="k", base_url="https://x/v4", timeout=60, max_retries=2
        )
        call_kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "glm-4.6v-flash"
        content = call_kwargs["messages"][0]["content"]
        assert content[0]["type"] == "text"
        assert "图片中的文字" in content[0]["text"]
        assert content[0]["text"].endswith("用户任务：请描述这张图")
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"] == DATA_URI

        # 返回结构
        assert result["text"] == "这是一只猫"
        assert result["model"] == "mock-vl"
        assert result["usage"]["total_tokens"] == 15

    def test_temperature_forwarded(self):
        """temperature 应透传给 chat.completions.create。"""
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = _mock_response()
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider(
                "k", "m", "https://x", temperature=0.7
            )
            provider.analyze(DATA_URI, "p")
        assert (
            fake_client.chat.completions.create.call_args.kwargs["temperature"] == 0.7
        )

    def test_analyze_multi_builds_multiple_image_blocks(self):
        """多图：一条 message 里应包含多张 image_url 块。"""
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = _mock_response()
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("k", "m", "https://x")
            result = provider.analyze_multi(
                ["data:image/jpeg;base64,AAA", "data:image/png;base64,BBB"],
                "对比这两张图",
            )
        content = fake_client.chat.completions.create.call_args.kwargs[
            "messages"
        ][0]["content"]
        images = [c for c in content if c["type"] == "image_url"]
        assert len(images) == 2
        assert result["text"] == "这是一只猫"

    def test_output_truncated_escalates_max_tokens(self):
        """finish_reason=length 时应升档重试 max_tokens。"""
        fake_client = mock.Mock()
        truncated = _mock_response(text="部分内容")
        truncated.choices[0].finish_reason = "length"
        complete = _mock_response(text="完整内容")
        complete.choices[0].finish_reason = "stop"
        fake_client.chat.completions.create.side_effect = [truncated, complete]
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("k", "m", "https://x")
            result = provider.analyze(DATA_URI, "p")
        assert result["text"] == "完整内容"
        max_tokens_used = [
            c.kwargs["max_tokens"]
            for c in fake_client.chat.completions.create.call_args_list
        ]
        assert max_tokens_used == [2048, 4096]  # 升档

    def test_reasoning_only_content_diagnosed(self):
        """只返回 reasoning_content 时应给出明确诊断。"""
        fake_client = mock.Mock()
        resp = _mock_response(text="")
        resp.choices[0].message.reasoning_content = "思考过程……"
        fake_client.chat.completions.create.return_value = resp
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("k", "m", "https://x")
            with pytest.raises(VisionProviderError, match="reasoning_content"):
                provider.analyze(DATA_URI, "p")

    def test_status_hint_in_error(self):
        """401 错误应附带修复指引。"""
        fake_client = mock.Mock()
        resp = SimpleNamespace(
            status_code=401,
            headers={},
            text="",
            url="https://x/chat/completions",
            request=SimpleNamespace(url="https://x/chat/completions", headers={}),
        )
        fake_client.chat.completions.create.side_effect = AuthenticationError(
            "Incorrect API key", response=resp, body=None
        )
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("bad-key", "m", "https://x")
            with pytest.raises(VisionProviderError, match="VISION_API_KEY"):
                provider.analyze(DATA_URI, "p")

    def test_analyze_returns_usage(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = _mock_response()
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("k", "m", "https://x")
            result = provider.analyze(DATA_URI, "p")
        assert result["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    def test_invalid_api_key_wrapped(self):
        """无效 API Key（401）应被包装为 VisionProviderError 并带上下文。"""
        fake_client = mock.Mock()
        resp = SimpleNamespace(
            status_code=401,
            headers={},
            text="",
            url="https://x/chat/completions",
            # openai 的 APIStatusError 需要 response.request
            request=SimpleNamespace(url="https://x/chat/completions", headers={}),
        )
        fake_client.chat.completions.create.side_effect = AuthenticationError(
            "Incorrect API key provided: sk-xxx", response=resp, body=None
        )
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("bad-key", "glm-4.6v-flash", "https://x")
            with pytest.raises(VisionProviderError, match="视觉模型失败|Incorrect API"):
                provider.analyze(DATA_URI, "p")

    def test_empty_response_wrapped(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = _mock_response(text="  ")
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("k", "m", "https://x")
            with pytest.raises(VisionProviderError, match="空内容"):
                provider.analyze(DATA_URI, "p")

    def test_network_error_wrapped(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.side_effect = TimeoutError("timed out")
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=fake_client,
        ):
            provider = OpenAICompatibleProvider("k", "m", "https://x")
            with pytest.raises(VisionProviderError, match="timed out"):
                provider.analyze(DATA_URI, "p")

    def test_rate_limit_rotates_to_next_key(self):
        first = mock.Mock()
        first.chat.completions.create.side_effect = FakeAPIError(429, "rate limited")
        second = mock.Mock()
        second.chat.completions.create.return_value = _mock_response()
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            side_effect=[first, second],
        ) as m_openai:
            provider = OpenAICompatibleProvider(
                "key-a", "m", "https://x", api_keys=["key-a", "key-b"]
            )
            result = provider.analyze(DATA_URI, "p")
        assert result["text"] == "这是一只猫"
        assert [call.kwargs["api_key"] for call in m_openai.call_args_list] == [
            "key-a",
            "key-b",
        ]

    def test_model_not_found_uses_fallback_model(self):
        client = mock.Mock()
        client.chat.completions.create.side_effect = [
            FakeAPIError(404, "model missing"),
            _mock_response(model="backup-vl"),
        ]
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=client,
        ):
            provider = OpenAICompatibleProvider(
                "k", "primary-vl", "https://x", models=["primary-vl", "backup-vl"]
            )
            result = provider.analyze(DATA_URI, "p")
        assert result["model"] == "backup-vl"
        assert [c.kwargs["model"] for c in client.chat.completions.create.call_args_list] == [
            "primary-vl",
            "backup-vl",
        ]

    def test_error_redacts_configured_key(self):
        client = mock.Mock()
        client.chat.completions.create.side_effect = FakeAPIError(
            401, "invalid credential secret-key-value"
        )
        with mock.patch(
            "deepseek_vision_mcp.providers.openai_compatible.OpenAI",
            return_value=client,
        ):
            provider = OpenAICompatibleProvider(
                "secret-key-value", "m", "https://x"
            )
            with pytest.raises(VisionProviderError) as exc_info:
                provider.analyze(DATA_URI, "p")
        assert "secret-key-value" not in str(exc_info.value)
        assert "***" in str(exc_info.value)


class TestProviderSwitch:
    """切换不同服务商配置时，应生成正确的 OpenAI 兼容客户端。"""

    def test_build_provider_zhihu(self):
        provider = build_provider(
            SimpleNamespace(
                provider="openai_compatible",
                api_key="z-key",
                model="glm-4.6v-flash",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                timeout_seconds=60,
            )
        )
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.model == "glm-4.6v-flash"
        assert provider.base_url == "https://open.bigmodel.cn/api/paas/v4"

    def test_build_provider_siliconflow(self):
        provider = build_provider(
            SimpleNamespace(
                provider="openai_compatible",
                api_key="s-key",
                model="Qwen/Qwen2.5-VL-7B-Instruct",
                base_url="https://api.siliconflow.cn/v1",
                timeout_seconds=60,
            )
        )
        assert provider.base_url == "https://api.siliconflow.cn/v1"
        assert provider.model == "Qwen/Qwen2.5-VL-7B-Instruct"

    def test_build_provider_dashscope(self):
        provider = build_provider(
            SimpleNamespace(
                provider="openai_compatible",
                api_key="d-key",
                model="qwen-vl-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout_seconds=60,
            )
        )
        assert provider.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert provider.model == "qwen-vl-plus"

    def test_build_provider_openai_alias(self):
        provider = build_provider(
            SimpleNamespace(
                provider="openai",
                api_key="o-key",
                model="gpt-4o",
                base_url="https://api.openai.com/v1",
                timeout_seconds=60,
            )
        )
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(VisionProviderError, match="未知的提供商"):
            build_provider(
                SimpleNamespace(
                    provider="weird-vendor",
                    api_key="k",
                    model="m",
                    base_url="https://x",
                    timeout_seconds=60,
                )
            )
