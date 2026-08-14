"""MCP Server 入口：注册 ``analyze_image`` / ``analyze_clipboard`` 工具。

使用官方 ``mcp`` Python SDK（FastMCP / MCPServer）实现。通过 stdio 与客户端
（DeepSeek Harness / Codex / Claude Desktop 等）通信。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

# 兼容 mcp SDK 1.x（FastMCP）与 2.x（MCPServer，FastMCP 的继任者）。
# 两者在注册工具、_tool_manager 结构上一致，这里按可用版本自动选择。
try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _ServerBase
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _ServerBase

from .clipboard import ClipboardError, save_clipboard_image
from .config import load_config
from .image_utils import ImageLoadError, ImageTooLargeError, load_image_as_base64
from .prompts import TASK_PROMPTS, TaskName
from .providers import build_provider
from .providers.base import VisionProviderError
from . import __version__

logger = logging.getLogger("deepseek_vision_mcp")

# 服务端实例名：客户端注册表中显示为 deepseek-vision
SERVER_NAME = "deepseek-vision"

# 未配置 API Key 时返回的引导文案（按免费服务商给出申请入口）
_KEY_GUIDANCE = (
    "缺少 VISION_API_KEY。请通过环境变量、.env 文件或 config.json 配置。\n"
    "免费申请入口：\n"
    "  智谱 GLM-4.6V-Flash（推荐，免费）：https://open.bigmodel.cn 控制台 → API Keys\n"
    "  硅基流动：https://cloud.siliconflow.cn 控制台 → API 密钥\n"
    "  通义千问：https://dashscope.console.aliyun.com 控制台 → API-KEY\n"
    "详见 README.md 的『快速开始』章节。"
)

# 工具 docstring 中的 task 说明（帮助主模型选择预置任务）


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
            "当用户发送图片路径、URL、base64 图片、剪贴板图片，或要求识别/描述"
            "图片时，调用 analyze_image / analyze_clipboard 工具。"
        ),
    )

    # 在闭包里持有配置与提供商实例，保证可测试（可注入 config）
    @mcp.tool()
    def analyze_image(
        image: str,
        prompt: Optional[str] = None,
        task: TaskName = "describe",
    ) -> str:
        """分析一张图片并返回识别结果（JSON）。

        Args:
            image: 图片输入，支持三种形式：
                1) 本地文件路径（如 ./screenshot.png 或绝对路径）
                2) http/https URL
                3) 纯 base64 字符串（可带 data: 前缀）
            prompt: 自定义对视觉模型的指令，优先级高于 task；不传时使用
                task 对应的预置提示词。
            task: 预置任务类型（不传 prompt 时生效）：
                describe（通用详细描述）、ocr（提取全部文字）、
                describe_ui（描述 UI 截图布局与状态）、
                diagnose_error（诊断错误截图并给出修复步骤）、
                understand_diagram（解读流程图/架构图）、
                analyze_chart（分析数据图表趋势与洞察）、
                code_from_screenshot（从代码截图提取代码）。
        """
        try:
            cfg = cfg_holder["config"]
            if cfg is None:
                cfg = load_config()  # 未配置 Key 时抛 ValueError

            effective_prompt = prompt or TASK_PROMPTS[task]
            logger.info("analyze_image 被调用，task=%s prompt=%r", task, effective_prompt)
            data_uri, mime = load_image_as_base64(
                image,
                max_size_kb=cfg.max_image_size_kb,
                download_timeout=cfg.download_timeout_seconds,
                allowed_formats=cfg.allowed_formats,
                allow_private=cfg.allow_private_urls,
            )
            logger.info("图片加载成功（%s，%.1f KB）", mime, len(data_uri) / 1024 / 1.37)

            provider = build_provider(cfg)
            try:
                outcome = provider.analyze(data_uri, effective_prompt)
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
            return _build_result(
                success=False,
                result=f"{exc}\n\n{_KEY_GUIDANCE}" if "VISION_API_KEY" in str(exc) else str(exc),
                error="CONFIG_ERROR",
            )
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

    @mcp.tool()
    def analyze_clipboard(
        prompt: Optional[str] = None,
        task: TaskName = "describe",
    ) -> str:
        """读取系统剪贴板中的图片并分析，返回识别结果（JSON）。

        当用户说「看看剪贴板里有什么」「我截图了」、复制/截屏了图片想直接
        分析时使用。支持 Windows / macOS / Linux。

        Args:
            prompt: 自定义对视觉模型的指令，优先级高于 task。
            task: 预置任务类型（不传 prompt 时生效）：
                describe（通用详细描述）、ocr（提取全部文字）、
                describe_ui（描述 UI 截图布局与状态）、
                diagnose_error（诊断错误截图并给出修复步骤）、
                understand_diagram（解读流程图/架构图）、
                analyze_chart（分析数据图表趋势与洞察）、
                code_from_screenshot（从代码截图提取代码）。
        """
        try:
            path = save_clipboard_image()
        except ClipboardError as exc:
            logger.info("剪贴板读取失败：%s", exc)
            return _build_result(
                success=False, result=str(exc), error="CLIPBOARD_ERROR"
            )
        try:
            return analyze_image(path, prompt=prompt, task=task)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @mcp.tool()
    def compare_images(images: list[str], prompt: Optional[str] = None) -> str:
        """对比分析多张图片（2-4 张），返回识别结果（JSON）。

        当用户说「对比这两张图」「这两张有什么区别」「看看这几张图」时使用。

        Args:
            images: 图片输入列表（2-4 张），每项支持本地路径 / http(s) URL /
                base64 字符串。
            prompt: 自定义对比指令；不传时自动生成
                「共 N 张图片，请对比分析相同点与不同点」。
        """
        try:
            cfg = cfg_holder["config"]
            if cfg is None:
                cfg = load_config()

            if not (2 <= len(images) <= 4):
                return _build_result(
                    success=False,
                    result="图片数量需在 2-4 张之间（实际收到 %d 张）。" % len(images),
                    error="INVALID_ARGUMENT",
                )

            logger.info("compare_images 被调用，共 %d 张图", len(images))
            data_uris = [
                load_image_as_base64(
                    img,
                    max_size_kb=cfg.max_image_size_kb,
                    download_timeout=cfg.download_timeout_seconds,
                    allowed_formats=cfg.allowed_formats,
                    allow_private=cfg.allow_private_urls,
                )[0]
                for img in images
            ]
            if not prompt:
                prompt = (
                    f"以下共有 {len(images)} 张图片，请对比分析它们的相同点与不同点，"
                    "并分别描述每张图片的关键内容。"
                )

            provider = build_provider(cfg)
            try:
                outcome = provider.analyze_multi(data_uris, prompt)
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
        except ImageLoadError as exc:
            logger.warning("图片加载失败：%s", exc)
            return _build_result(success=False, result=str(exc), error="IMAGE_LOAD_FAILED")
        except VisionProviderError as exc:
            logger.error("视觉模型调用失败：%s", exc)
            return _build_result(success=False, result=str(exc), error="VISION_API_ERROR")
        except Exception as exc:  # 兜底
            logger.exception("compare_images 发生未预期错误")
            return _build_result(
                success=False, result=f"内部错误：{exc}", error="INTERNAL_ERROR"
            )

    @mcp.tool()
    def vision_status() -> str:
        """返回视觉服务的配置与健康状态（JSON），用于诊断问题。

        当 analyze_image 等工具报错、或需要确认当前视觉模型配置时使用。
        """
        try:
            cfg = cfg_holder["config"]
            if cfg is None:
                cfg = load_config()
            configured = bool(cfg.api_key)
            status = {
                "version": __version__,
                "configured": configured,
                "model": cfg.model,
                "base_url": cfg.base_url,
                "provider": cfg.provider,
                "max_image_size_kb": cfg.max_image_size_kb,
                "timeout_seconds": cfg.timeout_seconds,
                "temperature": cfg.temperature,
                "allowed_formats": cfg.allowed_formats,
                "allow_private_urls": cfg.allow_private_urls,
                "api_key_masked": (cfg.api_key[:4] + "****") if configured else "",
            }
            status["success"] = configured
            status["result"] = (
                "视觉服务已就绪。" if configured
                else "未配置 VISION_API_KEY，请先配置（详见 README 快速开始）。"
            )
            return json.dumps(status, ensure_ascii=False)
        except Exception as exc:
            return json.dumps(
                {
                    "success": False,
                    "version": __version__,
                    "error": "CONFIG_ERROR",
                    "result": str(exc),
                },
                ensure_ascii=False,
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
