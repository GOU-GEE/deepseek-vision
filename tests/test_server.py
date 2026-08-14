"""MCP Server 端到端测试：analyze_image 工具的各类输入与错误处理。

通过注入假提供商（patch server.build_provider）与假图片加载
（patch server.load_image_as_base64）来避免真实网络/API 调用。
"""

from __future__ import annotations

import json
from unittest import mock

import deepseek_vision_mcp.server as server_module
from deepseek_vision_mcp.image_utils import ImageLoadError, ImageTooLargeError
from deepseek_vision_mcp.providers.base import VisionProviderError

DATA_URI = "data:image/jpeg;base64,QUJD"


class FakeProvider:
    """返回固定结果的假视觉模型。"""

    def __init__(self, text="识别文本", model="fake-vl"):
        self.text = text
        self.model = model
        self.closed = False

    def analyze(self, image_data_uri, prompt):
        return {
            "text": self.text,
            "model": self.model,
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    def close(self):
        self.closed = True


def _call_tool(config, image, prompt=None, task="describe"):
    """直接调用工具函数（FastMCP 装饰后仍保留原函数引用）。"""
    mcp = server_module.create_server(config=config)
    fn = mcp._tool_manager._tools["analyze_image"].fn
    return fn(image, prompt, task)


def _parse(raw: str) -> dict:
    return json.loads(raw)


class TestSuccess:
    def test_local_path_success(self, vision_config, jpg_path):
        fake = FakeProvider(text="这是一张测试图片")
        with mock.patch.object(server_module, "build_provider", return_value=fake):
            raw = _call_tool(vision_config, jpg_path, "请描述")
        out = _parse(raw)
        assert out["success"] is True
        assert out["result"] == "这是一张测试图片"
        assert out["model"] == "fake-vl"
        assert out["usage"]["total_tokens"] == 3
        assert fake.closed  # 提供商实例被正确释放

    def test_url_success(self, vision_config):
        fake = FakeProvider(text="URL 图片内容")
        with mock.patch.object(server_module, "build_provider", return_value=fake), \
             mock.patch.object(
                 server_module, "load_image_as_base64", return_value=(DATA_URI, "image/jpeg")
             ) as m_load:
            raw = _call_tool(vision_config, "https://example.com/a.png", "请描述")
        m_load.assert_called_once()
        assert m_load.call_args.args[0] == "https://example.com/a.png"
        out = _parse(raw)
        assert out["success"] is True
        assert out["result"] == "URL 图片内容"

    def test_base64_success(self, vision_config, jpg_base64):
        fake = FakeProvider(text="base64 图片内容")
        with mock.patch.object(server_module, "build_provider", return_value=fake), \
             mock.patch.object(
                 server_module, "load_image_as_base64", return_value=(DATA_URI, "image/jpeg")
             ):
            raw = _call_tool(vision_config, jpg_base64)
        out = _parse(raw)
        assert out["success"] is True
        assert out["result"] == "base64 图片内容"

    def test_default_prompt_used(self, vision_config, jpg_path):
        fake = FakeProvider()
        with mock.patch.object(server_module, "build_provider", return_value=fake):
            _call_tool(vision_config, jpg_path)
        assert fake.text == "识别文本"

    def test_same_image_and_prompt_uses_session_cache(self, vision_config):
        fake = FakeProvider(text="只调用一次")
        with mock.patch.object(
            server_module, "build_provider", return_value=fake
        ) as m_provider, mock.patch.object(
            server_module,
            "load_image_as_base64",
            return_value=(DATA_URI, "image/jpeg"),
        ):
            mcp = server_module.create_server(config=vision_config)
            fn = mcp._tool_manager._tools["analyze_image"].fn
            first = _parse(fn("a.jpg", "相同问题"))
            second = _parse(fn("a.jpg", "相同问题"))
        assert first["cached"] is False
        assert second["cached"] is True
        assert second["result"] == "只调用一次"
        m_provider.assert_called_once()


class TestErrors:
    def test_missing_file(self, vision_config, tmp_path):
        raw = _call_tool(vision_config, str(tmp_path / "nope.jpg"))
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "IMAGE_LOAD_FAILED"
        assert "不存在" in out["result"]

    def test_invalid_api_key(self, vision_config):
        """视觉模型报鉴权错误时，工具返回 success=false 与明确错误。"""
        with mock.patch.object(
            server_module,
            "build_provider",
            side_effect=VisionProviderError(
                "调用视觉模型失败（401 Unauthorized）：Incorrect API key"
            ),
        ):
            raw = _call_tool(vision_config, DATA_URI)
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "VISION_API_ERROR"
        assert "Incorrect API key" in out["result"]

    def test_image_too_large(self, vision_config):
        with mock.patch.object(
            server_module,
            "load_image_as_base64",
            side_effect=ImageTooLargeError("图片压缩后仍超过大小限制（10 KB）。"),
        ):
            raw = _call_tool(vision_config, "whatever")
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "IMAGE_TOO_LARGE"

    def test_garbage_input(self, vision_config):
        raw = _call_tool(vision_config, "这不是图片")
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "IMAGE_LOAD_FAILED"

    def test_unexpected_error_caught(self, vision_config):
        with mock.patch.object(
            server_module, "build_provider", side_effect=RuntimeError("boom")
        ):
            raw = _call_tool(vision_config, DATA_URI)
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "INTERNAL_ERROR"

    def test_prompt_is_forwarded(self, vision_config):
        """用户传入的 prompt 必须原样传给视觉模型。"""
        captured = {}

        class RecordingProvider(FakeProvider):
            def analyze(self, image_data_uri, prompt):
                captured["prompt"] = prompt
                captured["image"] = image_data_uri
                return {"text": "ok", "model": "m", "usage": {}}

        with mock.patch.object(
            server_module, "build_provider", return_value=RecordingProvider()
        ):
            _call_tool(vision_config, DATA_URI, "请提取图片中的文字")
        assert captured["prompt"] == "请提取图片中的文字"
        assert captured["image"] == DATA_URI

    def test_task_preset_used_when_no_prompt(self, vision_config):
        """不传 prompt 时，task 预置提示词应生效。"""
        captured = {}

        class RecordingProvider(FakeProvider):
            def analyze(self, image_data_uri, prompt):
                captured["prompt"] = prompt
                return {"text": "ok", "model": "m", "usage": {}}

        with mock.patch.object(
            server_module, "build_provider", return_value=RecordingProvider()
        ):
            _call_tool(vision_config, DATA_URI, task="ocr")
        assert "提取这张图片中的全部文字" in captured["prompt"]

    def test_prompt_overrides_task(self, vision_config):
        """显式 prompt 应优先于 task 预置。"""
        captured = {}

        class RecordingProvider(FakeProvider):
            def analyze(self, image_data_uri, prompt):
                captured["prompt"] = prompt
                return {"text": "ok", "model": "m", "usage": {}}

        with mock.patch.object(
            server_module, "build_provider", return_value=RecordingProvider()
        ):
            _call_tool(vision_config, DATA_URI, "自定义问题", task="ocr")
        assert captured["prompt"] == "自定义问题"

    def test_default_task_is_describe(self, vision_config):
        captured = {}

        class RecordingProvider(FakeProvider):
            def analyze(self, image_data_uri, prompt):
                captured["prompt"] = prompt
                return {"text": "ok", "model": "m", "usage": {}}

        with mock.patch.object(
            server_module, "build_provider", return_value=RecordingProvider()
        ):
            _call_tool(vision_config, DATA_URI)
        assert captured["prompt"] == "请详细描述这张图片的内容"


class TestClipboard:
    def test_analyze_clipboard_success(self, vision_config, tmp_path):
        """剪贴板有图时：保存→分析→清理临时文件。"""
        clip_path = tmp_path / "clip.png"
        clip_path.write_bytes(b"fake-png")
        fake = FakeProvider(text="剪贴板图片内容")
        with mock.patch.object(server_module, "build_provider", return_value=fake), \
             mock.patch.object(
                 server_module, "save_clipboard_image", return_value=str(clip_path)
             ) as m_save, \
             mock.patch.object(server_module, "load_image_as_base64",
                               return_value=(DATA_URI, "image/png")) as m_load, \
             mock.patch.object(server_module.os, "unlink") as m_unlink:
            mcp = server_module.create_server(config=vision_config)
            fn = mcp._tool_manager._tools["analyze_clipboard"].fn
            raw = fn()
        out = _parse(raw)
        assert out["success"] is True
        assert out["result"] == "剪贴板图片内容"
        m_save.assert_called_once()
        m_load.assert_called_once()
        m_unlink.assert_called_once_with(str(clip_path))

    def test_analyze_clipboard_no_image(self, vision_config):
        """剪贴板无图时应返回 CLIPBOARD_ERROR 且不调用分析。"""
        with mock.patch.object(
            server_module,
            "save_clipboard_image",
            side_effect=server_module.ClipboardError("剪贴板中没有图片。"),
        ), mock.patch.object(server_module, "build_provider") as m_provider:
            mcp = server_module.create_server(config=vision_config)
            fn = mcp._tool_manager._tools["analyze_clipboard"].fn
            raw = fn()
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "CLIPBOARD_ERROR"
        m_provider.assert_not_called()

    def test_missing_key_error_has_guidance(self, monkeypatch):
        """未配置 Key 时（惰性加载触发校验），返回 CONFIG_ERROR + 申请指引。"""
        # 清空环境中可能的 VISION_* 变量，模拟全新用户
        for k in list(__import__("os").environ):
            if k.startswith("VISION_"):
                monkeypatch.delenv(k)
        mcp = server_module.create_server(config=None)
        fn = mcp._tool_manager._tools["analyze_image"].fn
        raw = fn(DATA_URI)
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "CONFIG_ERROR"
        assert "open.bigmodel.cn" in out["result"]      # 智谱申请入口
        assert "siliconflow.cn" in out["result"]        # 硅基流动申请入口
        assert "dashscope" in out["result"]             # 通义千问申请入口


class TestCompareImages:
    def _call(self, config, images, prompt=None):
        mcp = server_module.create_server(config=config)
        fn = mcp._tool_manager._tools["compare_images"].fn
        return fn(images, prompt)

    def test_compare_success(self, vision_config):
        """多图对比：应逐张加载并调用 analyze_multi。"""
        captured = {}

        class RecordingProvider(FakeProvider):
            def analyze_multi(self, uris, prompt):
                captured["uris"] = uris
                captured["prompt"] = prompt
                return {"text": "对比结果", "model": "m", "usage": {}}

        with mock.patch.object(
            server_module, "build_provider", return_value=RecordingProvider()
        ), mock.patch.object(
            server_module, "load_image_as_base64",
            side_effect=lambda img, **kw: (f"data:image/jpeg;base64,{img}", "image/jpeg"),
        ):
            raw = self._call(vision_config, ["a.jpg", "b.jpg"])
        out = _parse(raw)
        assert out["success"] is True
        assert out["result"] == "对比结果"
        assert len(captured["uris"]) == 2
        assert "2 张图片" in captured["prompt"]  # 自动注入对比指令

    def test_compare_custom_prompt(self, vision_config):
        captured = {}

        class RecordingProvider(FakeProvider):
            def analyze_multi(self, uris, prompt):
                captured["prompt"] = prompt
                return {"text": "ok", "model": "m", "usage": {}}

        with mock.patch.object(
            server_module, "build_provider", return_value=RecordingProvider()
        ), mock.patch.object(
            server_module, "load_image_as_base64",
            return_value=(DATA_URI, "image/jpeg"),
        ):
            self._call(vision_config, ["a.jpg", "b.jpg"], "这两张图哪个更好？")
        assert captured["prompt"] == "这两张图哪个更好？"

    def test_compare_requires_2_to_4(self, vision_config):
        raw = self._call(vision_config, ["only_one.jpg"])
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "INVALID_ARGUMENT"

    def test_compare_load_failure(self, vision_config):
        with mock.patch.object(
            server_module,
            "load_image_as_base64",
            side_effect=ImageLoadError("图片文件不存在：x.jpg"),
        ):
            raw = self._call(vision_config, ["x.jpg", "y.jpg"])
        out = _parse(raw)
        assert out["success"] is False
        assert out["error"] == "IMAGE_LOAD_FAILED"


class TestVisionStatus:
    def test_status_configured(self, vision_config):
        mcp = server_module.create_server(config=vision_config)
        fn = mcp._tool_manager._tools["vision_status"].fn
        raw = json.loads(fn())
        assert raw["configured"] is True
        assert raw["model"] == "glm-4.6v-flash"
        assert raw["api_key_masked"] == "****"
        assert raw["api_key_count"] == 1

    def test_status_not_configured(self, monkeypatch):
        for k in list(__import__("os").environ):
            if k.startswith("VISION_"):
                monkeypatch.delenv(k)
        mcp = server_module.create_server(config=None)
        fn = mcp._tool_manager._tools["vision_status"].fn
        raw = json.loads(fn())
        assert raw["success"] is False
        assert raw["error"] == "CONFIG_ERROR"
        assert "VISION_API_KEY" in raw["result"]


class TestServerInstance:
    def test_create_server_registers_tool(self, vision_config):
        mcp = server_module.create_server(config=vision_config)
        assert "analyze_image" in mcp._tool_manager._tools

    def test_module_level_server_uses_default_config(self):
        """模块级实例应能创建（配置缺 key 时以未校验方式兜底创建）。"""
        assert server_module.mcp is not None
