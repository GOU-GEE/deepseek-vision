"""从客户端侧完成 MCP + 真实视觉 API + 会话缓存的一键验收。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(image: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "deepseek_vision_mcp"],
        env=os.environ.copy(),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            expected = {
                "analyze_clipboard",
                "analyze_image",
                "compare_images",
                "vision_status",
            }
            missing = expected.difference(names)
            if missing:
                raise RuntimeError(f"MCP 工具缺失：{', '.join(sorted(missing))}")
            print(f"[OK] MCP stdio 握手成功，工具：{', '.join(names)}")

            status_result = await session.call_tool("vision_status", {})
            status = json.loads(status_result.content[0].text)
            if not status.get("success"):
                raise RuntimeError(status.get("result", "vision_status 未就绪"))
            print(
                f"[OK] 视觉服务就绪，模型链：{' -> '.join(status.get('models', []))}，"
                f"Key 数量：{status.get('api_key_count', 0)}"
            )

            arguments = {
                "image": str(image.resolve()),
                "prompt": "请用一句话准确描述这张图片，作为安装验收。",
            }
            first_result = await session.call_tool("analyze_image", arguments)
            first = json.loads(first_result.content[0].text)
            if not first.get("success"):
                raise RuntimeError(first.get("result", "首次识图失败"))
            if first.get("cached"):
                raise RuntimeError("首次识图意外命中缓存，无法确认真实 API 调用")
            print(f"[OK] 真实识图成功，模型：{first.get('model')}")
            print(f"     结果：{first.get('result')}")

            second_result = await session.call_tool("analyze_image", arguments)
            second = json.loads(second_result.content[0].text)
            if not second.get("success") or not second.get("cached"):
                raise RuntimeError("重复调用未命中会话缓存")
            print("[OK] 重复调用命中会话缓存（cached=true，未再次消耗视觉 API）")


def main() -> int:
    parser = argparse.ArgumentParser(description="验收 deepseek-vision-mcp 安装")
    parser.add_argument(
        "image",
        nargs="?",
        default="examples/test_image.jpg",
        help="用于真实识图验收的图片路径",
    )
    args = parser.parse_args()
    image = Path(args.image)
    if not image.is_file():
        print(f"[FAIL] 测试图片不存在：{image}", file=sys.stderr)
        return 1
    try:
        asyncio.run(verify(image))
    except Exception as exc:
        print(f"[FAIL] 安装验收失败：{exc}", file=sys.stderr)
        return 1
    print("[PASS] 从 MCP 客户端到视觉 API 的完整链路验收通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
