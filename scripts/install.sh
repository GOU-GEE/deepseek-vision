#!/usr/bin/env bash
# 一键安装脚本：创建虚拟环境、安装依赖、生成示例配置。
# 用法: bash scripts/install.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
echo "==> 使用 Python: $($PYTHON --version)"

if [ ! -d .venv ]; then
  echo "==> 创建虚拟环境 .venv"
  $PYTHON -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 升级 pip"
python -m pip install --upgrade pip

echo "==> 安装 deepseek-vision-mcp（含开发依赖）"
python -m pip install -e ".[dev]"

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "==> 生成 .env（请编辑填入你的 API Key）"
  cp .env.example .env
fi

echo
echo "==> 安装完成！下一步："
echo "    1) 编辑 .env，填入 VISION_API_KEY"
echo "    2) deepseek-vision-mcp --check   # 校验配置"
echo "    3) deepseek-vision-mcp           # 启动 MCP Server"
