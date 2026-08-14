#!/usr/bin/env bash
# MCP Server 冒烟测试：用 test_mcp 客户端调用 analyze_image 工具。
# 用法: bash scripts/test_mcp.sh [图片路径]
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${1:-examples/test_image.jpg}"

if [ ! -f .env ]; then
  echo "[!] 未找到 .env，请先: cp .env.example .env 并填入 VISION_API_KEY" >&2
  exit 1
fi

echo "==> 校验配置"
python -m deepseek_vision_mcp --check

echo "==> 直接调用视觉模型识别: $IMAGE"
python -m deepseek_vision_mcp --test-image "$IMAGE"

echo
echo "==> 冒烟测试完成。若上方输出包含 result 文本，说明集成正常。"
