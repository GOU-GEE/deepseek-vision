# Changelog

## v0.3.0（2026-08-15）

首个正式发布版本。为 DeepSeek Harness 等纯文本模型提供完整的视觉能力：
MCP Server（Python 包）+ DSH 原生插件（npm 包）+ 自动触发的 vision Skill。

### 🚀 新增功能

- **4 个 MCP 工具**：`analyze_image`（单图，支持本地路径/URL/base64）、
  `analyze_clipboard`（剪贴板读图，Win/macOS/Linux）、`compare_images`
  （2-4 张多图对比）、`vision_status`（健康检查）
- **7 种预置任务**（`task` 参数）：通用描述 / OCR / UI 截图 / 报错诊断 /
  图表解读 / 代码提取 / 流程图理解，无需自行拼 prompt
- **DSH 原生插件**：可视化配置页（设置 → 插件 → DeepSeek Vision）、
  粘贴/拖拽图片自动触发、Key 存 DSH 官方凭据存储（不落库/不回显/不进上下文）
- **自动运行时**：无需 GUI PATH 有 Python/Node——优先系统 Python 3.10+，
  否则自动下载固定版本 uv 0.12.5 + 隔离 CPython 3.12 + 安装内置 wheel

### 🛡️ 容错与安全

- 多 Key 轮换（`VISION_API_KEYS`）、同服务商模型降级（`VISION_MODELS`）、
  跨服务商备用链（`VISION_FALLBACK_API_KEY` / `VISION_FALLBACKS_JSON`）
- 免费模型限流韧性：`Retry-After` 感知指数退避、全局请求预算（默认 4 次）、
  故障端点熔断（默认 90 秒）
- 识别结果缓存（LRU + TTL，`VISION_CACHE_*`），同图同问秒回 `cached=true`
- SSRF 防护（URL 下载拒私网/元数据地址、重定向复检）
- 输出 token 升档重试、空内容诊断（区分截断与 reasoning_content）、
  HTTP 状态码 → 中文修复指引
- Key 全程不写入 Git 仓库、日志、模型上下文与页面返回数据

### 📦 交付形态

- PyPI：`deepseek-vision-mcp==0.3.0`（`pip install deepseek-vision-mcp`）
- npm：`dsh-plugin-deepseek-vision@0.3.0`
  （`dsh plugin --profile web add dsh-plugin-deepseek-vision`）
- GitHub：源码 + Release + CI 徽章
- 默认视觉模型：智谱免费 `glm-4.6v-flash`；支持硅基流动 / 通义千问 /
  OpenAI / 任意 OpenAI 兼容接口

### ✅ 质量

- 94 个 Python pytest 用例 + 18 个 DSH 插件 Node 测试
- MCP SDK 1.2.0 / 1.29.0 / 2.0.0 兼容矩阵
- 真实 MCP stdio 握手验证；Ruff 检查；wheel/sdist 构建与 Twine 校验
- GitHub Actions 测试 + 发布（PyPI/npm Trusted Publishing）工作流

### 🧭 快速开始

```bash
# Python（任意 MCP 客户端）
pip install deepseek-vision-mcp
cp .env.example .env   # 填入 VISION_API_KEY
deepseek-vision-mcp

# DeepSeek Harness 一键插件
dsh plugin --profile web add dsh-plugin-deepseek-vision
cp -r skills/vision ~/.dsh/skills/
```
