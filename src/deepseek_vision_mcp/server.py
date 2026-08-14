"""MCP Server 入口：注册 ``analyze_image`` 工具。

使用官方 ``mcp`` Python SDK（FastMCP / MCPServer）实现。通过 stdio 与客户端
（DeepSeek Harness / Codex / Claude Desktop 等）通信。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

# 兼容 mcp SDK 1.x（FastMCP）与 2.x（MCPServer，FastMCP 的继任者）。
# 两者在注册工具、_tool_manager 结构上一致，这里按可用版本自动选择。
try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _ServerBase
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _ServerBase

from .config import load_config
from .image_utils import ImageLoadError, ImageTooLargeError, load_image_as_base64
from .providers import build_provider
from .providers.base import VisionProviderError

logger = logging.getLogger("deepseek_vision_mcp")

DEFAULT_PROMPT = "请详细描述这张图片的内容"

# 服务端实例名：客户端注册表中显示为 deepseek-vision
SERVER_NAME = "deepseek-vision"


def _build_result(
    success: bool,
    result: str,
    model: Optional[str] = None,
    usage: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> str:
    """把结果统一序列化为 JSON 字符串返回给主模型。"""
    payload = {
        "success": success,
        "result": result,
        "model": model,
        "usage": usage or {},
    }
    if error is not None:
        payload["error"] = error
    return json.dumps(payload, ensure_ascii=False)


def create_server(config: Optional[Any] = None) -> _ServerBase:
    """创建（并配置）MCP Server 实例。

    参数:
        config: VisionConfig；为 None 时在工具被调用时惰性加载
            （因此未配置 API Key 也能启动 Server，调用工具时返回清晰错误）。
    """
    cfg_holder: Dict[str, Any] = {"config": config}

    mcp = _ServerBase(
        SERVER_NAME,
        instructions=(
            "为 DeepSeek 等纯文本模型提供图片理解能力。"
            "当用户发送图片路径、URL、base64 图片，或要求识别/描述图片时，"
            "调用 analyze_image 工具。"
        ),
    )

    # 在闭包里持有配置与提供商实例，保证可测试（可注入 config）
    @mcp.tool()
    def analyze_image(image: str, prompt: str = DEFAULT_PROMPT) -> str:
        """分析一张图片并返回识别结果（JSON）。

        Args:
            image: 图片输入，支持三种形式：
                1) 本地文件路径（如 ./screenshot.png 或绝对路径）
                2) http/https URL
                3) 纯 base64 字符串（可带 data: 前缀）
            prompt: 对视觉模型的任务描述，例如"提取图片中的文字"、
                "描述场景"、"指出错误信息"。默认为"请详细描述这张图片的内容"。
        """
        try:
            cfg = cfg_holder["config"]
            if cfg is None:
                cfg = load_config()  # 未配置 Key 时抛 ValueError

            logger.info("analyze_image 被调用，prompt=%r", prompt)
            data_uri, mime = load_image_as_base64(
                image,
                max_size_kb=cfg.max_image_size_kb,
                download_timeout=cfg.download_timeout_seconds,
                allowed_formats=cfg.allowed_formats,
            )
            logger.info("图片加载成功（%s，%.1f KB）", mime, len(data_uri) / 1024 / 1.37)

            provider = build_provider(cfg)
            try:
                outcome = provider.analyze(data_uri, prompt)
            finally:
                provider.close()

            return _build_result(
                success=True,
                result=outcome["text"],
                model=outcome.get("model") or cfg.model,
                usage=outcome.get("usage"),
            )
        except ValueError as exc:
            logger.error("配置错误：%s", exc)
            return _build_result(success=False, result=str(exc), error="CONFIG_ERROR")
        except ImageTooLargeError as exc:
            logger.warning("图片超限：%s", exc)
            return _build_result(success=False, result=str(exc), error="IMAGE_TOO_LARGE")
        except ImageLoadError as exc:
            logger.warning("图片加载失败：%s", exc)
            return _build_result(success=False, result=str(exc), error="IMAGE_LOAD_FAILED")
        except VisionProviderError as exc:
            logger.error("视觉模型调用失败：%s", exc)
            return _build_result(success=False, result=str(exc), error="VISION_API_ERROR")
        except Exception as exc:  # 兜底，避免工具崩溃导致会话中断
            logger.exception("analyze_image 发生未预期错误")
            return _build_result(
                success=False, result=f"内部错误：{exc}", error="INTERNAL_ERROR"
            )

    return mcp


def run() -> None:
    """以 stdio 方式启动 MCP Server（供 main.py 调用）。"""
    mcp = create_server()
    mcp.run()


# 模块级实例：`python -m deepseek_vision_mcp` 与调试工具均可用
mcp = create_server()

if __name__ == "__main__":
    run()
