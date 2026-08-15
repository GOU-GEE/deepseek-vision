"""命令行入口。

用法：
    python -m deepseek_vision_mcp            # 以 stdio 启动 MCP Server
    deepseek-vision-mcp                      # 等价（安装后可用）
    deepseek-vision-mcp --check              # 校验配置是否就绪
    deepseek-vision-mcp --check-clipboard    # 校验剪贴板图片读取（无需 API Key）
    deepseek-vision-mcp --test-image PATH    # 本地自测：不经 MCP，直接识别一张图
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import __version__
from .config import load_config
from .image_utils import load_image_as_base64
from .providers import build_provider


def _setup_logging() -> None:
    """MCP stdio 协议下 stdout 是 JSON-RPC 通道，日志必须全部走 stderr。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )


def _print_banner(cfg) -> None:
    """启动横幅（stderr），肉眼即可确认生效配置。"""
    key_state = "已配置" if cfg.api_key else "未配置(!!)"
    print(
        f"[deepseek-vision-mcp v{__version__}] provider={cfg.provider} "
        f"model={cfg.model} base_url={cfg.base_url} API Key:{key_state}",
        file=sys.stderr,
    )


def _contains_keyboard_interrupt(exc: BaseException) -> bool:
    """兼容 Python 3.10，并识别 AnyIO 在 3.11+ 包装的异常组。"""
    if isinstance(exc, KeyboardInterrupt):
        return True
    return any(
        _contains_keyboard_interrupt(nested)
        for nested in getattr(exc, "exceptions", ())
        if isinstance(nested, BaseException)
    )


def _cmd_check() -> int:
    """校验配置与依赖是否就绪。"""
    try:
        cfg = load_config()
    except Exception as exc:
        print(f"[FAIL] 配置校验失败：{exc}", file=sys.stderr)
        return 1
    print("[OK] 配置就绪")
    print(f"     提供商   : {cfg.provider}")
    print(f"     base_url : {cfg.base_url}")
    print(f"     models   : {' -> '.join(cfg.models)}")
    print(f"     API Keys : {len(cfg.api_keys)} 个")
    print(f"     图片限制 : {cfg.max_image_size_kb} KB，格式 {', '.join(cfg.allowed_formats)}")
    print(f"     温度     : {cfg.temperature}")
    print(
        f"     会话缓存 : {'开启' if cfg.cache_enabled else '关闭'}"
        f"（最多 {cfg.cache_max_entries} 条，TTL {cfg.cache_ttl_seconds}s）"
    )
    if not cfg.api_key:
        print("[WARN] VISION_API_KEY 为空，调用 analyze_image 会失败", file=sys.stderr)
    return 0


def _cmd_check_clipboard() -> int:
    """校验剪贴板图片读取是否可用（不依赖 API Key）。"""
    try:
        from .clipboard import ClipboardError, save_clipboard_image

        path = save_clipboard_image()
    except ClipboardError as exc:
        print(f"[FAIL] 剪贴板图片读取失败：{exc}", file=sys.stderr)
        print("[提示] 请先复制一张图片（如截图）到剪贴板再试。", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[FAIL] 剪贴板读取异常：{exc}", file=sys.stderr)
        return 1
    import os

    try:
        os.unlink(path)
    except OSError:
        pass
    print("[OK] 剪贴板图片读取成功（临时文件已清理）")
    return 0


def _cmd_test_image(path: str, prompt: str) -> int:
    """本地自测：直接调用视觉模型识别一张图片（不经过 MCP）。"""
    cfg = load_config()
    try:
        data_uri, mime = load_image_as_base64(
            path,
            max_size_kb=cfg.max_image_size_kb,
            download_timeout=cfg.download_timeout_seconds,
            allowed_formats=cfg.allowed_formats,
            allow_private=cfg.allow_private_urls,
        )
    except Exception as exc:
        print(f"[FAIL] 图片加载失败：{exc}", file=sys.stderr)
        return 1
    print(f"[OK] 图片加载成功（{mime}）")
    provider = build_provider(cfg)
    try:
        outcome = provider.analyze(data_uri, prompt)
    except Exception as exc:
        print(f"[FAIL] 视觉模型调用失败：{exc}", file=sys.stderr)
        return 1
    finally:
        provider.close()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(
        prog="deepseek-vision-mcp",
        description="DeepSeek 视觉能力 MCP Server（OpenAI 兼容视觉模型）。",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="校验配置是否就绪（不启动 Server）。",
    )
    parser.add_argument(
        "--check-clipboard",
        action="store_true",
        help="校验剪贴板图片读取（无需 API Key）。",
    )
    parser.add_argument(
        "--test-image",
        metavar="PATH_OR_URL",
        help="本地自测：直接识别一张图片并打印结果。",
    )
    parser.add_argument(
        "--prompt",
        default="请详细描述这张图片的内容",
        help="与 --test-image 搭配的自定义提示词。",
    )
    args = parser.parse_args(argv)

    if args.check:
        return _cmd_check()
    if args.check_clipboard:
        return _cmd_check_clipboard()
    if args.test_image:
        return _cmd_test_image(args.test_image, args.prompt)

    # 默认：以 stdio 启动 MCP Server
    from .server import run

    try:
        _print_banner(load_config())
    except Exception:
        pass  # 未配置 Key 也能启动，调用工具时才报错
    try:
        run()
    except BaseException as exc:
        # MCP 2.x / AnyIO 可能把 Ctrl-C 包在 BaseExceptionGroup 中。正常退出时
        # 不向 DSH 用户倾倒数十行异常栈；其他 BaseException 仍原样抛出。
        if _contains_keyboard_interrupt(exc):
            return 130
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
