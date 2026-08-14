"""命令行入口。

用法：
    python -m deepseek_vision_mcp            # 以 stdio 启动 MCP Server
    deepseek-vision-mcp                      # 等价（安装后可用）
    deepseek-vision-mcp --check              # 校验配置是否就绪
    deepseek-vision-mcp --test-image PATH    # 本地自测：不经 MCP，直接识别一张图
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_config
from .image_utils import load_image_as_base64
from .providers import build_provider


def _cmd_check() -> int:
    """校验配置与依赖是否就绪。"""
    try:
        cfg = load_config()
    except Exception as exc:
        print(f"[FAIL] 配置校验失败：{exc}", file=sys.stderr)
        return 1
    print(f"[OK] 配置就绪")
    print(f"     提供商   : {cfg.provider}")
    print(f"     base_url : {cfg.base_url}")
    print(f"     model    : {cfg.model}")
    print(f"     图片限制 : {cfg.max_image_size_kb} KB，格式 {', '.join(cfg.allowed_formats)}")
    if not cfg.api_key:
        print("[WARN] VISION_API_KEY 为空，调用 analyze_image 会失败", file=sys.stderr)
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
    if args.test_image:
        return _cmd_test_image(args.test_image, args.prompt)

    # 默认：以 stdio 启动 MCP Server
    from .server import run

    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
