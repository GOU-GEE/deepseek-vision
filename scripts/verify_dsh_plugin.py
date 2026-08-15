"""验证 DSH npm Bundle 的托管运行时到 MCP 工具注册完整链路。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "analyze_clipboard",
    "analyze_image",
    "compare_images",
    "vision_status",
}


async def verify(launcher: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="dsh-vision-runtime-") as home:
        environment = {
            **os.environ,
            "DSH_HOME": home,
            "VISION_PYTHON": sys.executable,
            "VISION_API_KEY": "managed-runtime-smoke-key",
        }
        params = StdioServerParameters(
            command="node",
            args=[str(launcher.resolve())],
            env=environment,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                if names != EXPECTED_TOOLS:
                    raise RuntimeError(f"DSH 托管运行时工具不匹配：{sorted(names)}")
                result = await session.call_tool("vision_status", {})
                payload = json.loads(result.content[0].text)
                if not payload.get("configured") or payload.get("version") != "0.2.0":
                    raise RuntimeError(f"DSH 托管运行时状态异常：{payload}")


def main() -> int:
    launcher = Path("plugins/dsh-plugin-deepseek-vision/launcher.js")
    if not launcher.is_file():
        print(f"[FAIL] 找不到 DSH launcher：{launcher}", file=sys.stderr)
        return 1
    try:
        asyncio.run(verify(launcher))
    except Exception as exc:
        print(f"[FAIL] DSH 托管运行时验收失败：{exc}", file=sys.stderr)
        return 1
    print("[PASS] DSH 托管运行时 → MCP 握手 → 4 个工具注册全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
