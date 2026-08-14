#!/usr/bin/env bash
# MCP Server 完整验收：stdio 握手 + 真实识图 + 会话缓存。
# 用法: bash scripts/test_mcp.sh [图片路径]
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${1:-examples/test_image.jpg}"

if [ ! -f .env ]; then
  echo "[!] 未找到 .env，请先: cp .env.example .env 并填入 VISION_API_KEY" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
exec "$PYTHON_BIN" scripts/verify_install.py "$IMAGE"
