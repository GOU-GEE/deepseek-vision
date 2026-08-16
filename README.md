# deepseek-vision-mcp

[![CI](https://github.com/GOU-GEE/deepseek-vision/actions/workflows/test.yml/badge.svg)](https://github.com/GOU-GEE/deepseek-vision/actions/workflows/test.yml)
[![Publish](https://github.com/GOU-GEE/deepseek-vision/actions/workflows/publish.yml/badge.svg)](https://github.com/GOU-GEE/deepseek-vision/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/deepseek-vision-mcp?color=3776AB&label=PyPI)](https://pypi.org/project/deepseek-vision-mcp/)
[![npm version](https://img.shields.io/npm/v/dsh-plugin-deepseek-vision?color=CB3837&label=npm)](https://www.npmjs.com/package/dsh-plugin-deepseek-vision)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Awesome DSH Plugin](https://awesome-dsh-plugin.com/badge.svg)](https://awesome-dsh-plugin.com)

给 **DeepSeek（及其他纯文本大模型）装上「眼睛」** 的开源 MCP Server。

DeepSeek 系列模型是纯文本模型，无法直接识别图片。本项目的思路是：
通过 **MCP Server 暴露一个 `analyze_image` 工具**，把图片交给第三方
**OpenAI 兼容的视觉模型 API**（智谱 GLM-4.6V、硅基流动 Qwen2.5-VL、
通义千问 qwen-vl-plus 等）识别，再把识别文本返回给主模型。
配合项目自带的 **Skill 文件**，DeepSeek 主模型在遇到图片时会**自动**调用
该工具——对用户来说，就像 DeepSeek 突然会「看图」了。

> 视觉识别能力由第三方模型提供，图片会被发送到对应服务商的 API。
> 请阅读文末的[隐私说明](#隐私说明)。

---

## 🚀 一句话安装（复制给 AI 助手，免手动操作）

主要在 DeepSeek Harness 中使用时，复制下面的推荐提示词给助手。它会从全新克隆构建
本仓库的 DSH Bundle、安装到桌面版共用的 Web profile，并引导你在 DSH 可视化页面中
安全填写 Key，最后完成自动托管 Python 与真实图片验收。
其他 MCP 客户端请使用后面的通用版。

> **关于 API Key（请先读）**：
> - ✅ 默认方案使用智谱 `glm-4.6v-flash`：安装后在 DSH 的
>   `设置 → 插件 → 插件配置 → DeepSeek Vision` 中填写你在
>   `https://open.bigmodel.cn` 申请的 Key。
> - ⚠️ Key、模型和 Base URL 必须属于同一家服务商。硅基流动或通义千问的 Key 也能用，
>   但必须同时把对应的 `VISION_MODEL` 与 `VISION_BASE_URL` 告诉助手，不能套用智谱默认值。
> - 🔒 免费或付费 Key 都不必发给 AI 助手：可视化页面不会回显 Key，凭据由 DSH
>   官方凭据存储保存，不会写进仓库或普通配置文件。

**DeepSeek Harness 推荐版（一会话从零部署并验收）**：

```text
请在一个会话内从零安装并验收 https://github.com/GOU-GEE/deepseek-vision 的 DSH
插件，让 macOS DeepSeek Harness 桌面版中的文本模型获得视觉能力（默认智谱免费模型
glm-4.6v-flash）：
1. 在全新的、不复用旧仓库或虚拟环境的目录克隆 main，确认 Node >=22.19、Python >=3.10，
   并运行 corepack enable、corepack prepare pnpm@11.7.0 --activate。
2. 进入 plugins/dsh-plugin-deepseek-vision，运行 npm ci --ignore-scripts、npm test，
   再以可用的 Python 设置 VISION_BUILD_PYTHON 并运行 npm pack；检查 tarball 内含 LICENSE
   和 runtime/deepseek_vision_mcp-<pyproject 中的版本>-py3-none-any.whl
   （当前 main 为 deepseek_vision_mcp-0.4.1-py3-none-any.whl）。
3. 确认 `/Applications/DeepSeek Harness.app` 存在并读取它的实际 DSH 版本；先让我用
   Cmd+Q 完全退出桌面版，再使用 App 内置的 DSH CLI，把源码构建的 tarball 合并安装到
   默认 `web` profile。不要尝试安装尚未发布的 npm 版本，不覆盖整个 profile。用同一
   CLI 的 `--profile web --dump-config` 确认 deepseek-vision-host、deepseek-vision-mcp
   和插件内置 launcher.js 均已加载；若不是 macOS 桌面版，再回退到同版本 npx dsh 命令。
4. 让我重新打开 DeepSeek Harness，进入
   `设置 → 插件 → 插件配置 → DeepSeek Vision`，选择“智谱 GLM（推荐免费）”，确认模型
   自动为 glm-4.6v-flash、Base URL 自动为 https://open.bigmodel.cn/api/paas/v4；让我亲自
   在密码框填写 Key，点击“保存”和“测试连接”。不得向我索取或读取 Key，测试连接失败时
   展示页面错误。保存后按页面提示 Cmd+Q 并重新打开，使 MCP 使用新配置。
5. 从仓库根目录运行 python scripts/verify_dsh_plugin.py，必须通过真实 MCP stdio 握手、
   4 个工具和 vision_status；然后在重新打开的桌面版中选择文本版 DeepSeek，把
   examples/test_image.jpg 粘贴或拖入输入框，确认输入框上方出现不超过输入框宽度的
   缩略图卡带、输入框内不显示工具指令长文本；不输入文字直接发送时，确认自动注入
   analyze_image 指令且工具实际调用成功、返回 model=glm-4.6v-flash，发送后缩略图卡带
   自动关闭。再发同图同问题，确认 cached=true。
6. 每一步失败立即停止并展示完整错误；配置只做合并，不覆盖用户原有 DSH profile，
   不删除旧安装。最后汇报克隆路径、tarball、DSH profile、托管运行时路径及全部验收结果。
```

**其他 MCP 客户端通用版（Claude Code / Codex / OpenCode 等）**：

```text
请帮我安装并启用 deepseek-vision-mcp（GitHub: https://github.com/GOU-GEE/deepseek-vision），
它通过 MCP 工具 analyze_image 让纯文本模型具备图片识别能力。请按以下步骤自动完成：

[我的智谱免费 API Key（可选；付费 Key 请删掉这一行）: YOUR_ZHIPU_FREE_API_KEY]

1. 创建一个全新的安装目录（如 `deepseek-vision-fresh`；若已存在则换一个未占用的后缀，
   不复用、不覆盖、不删除旧安装），在其中克隆 main：
   `git clone --branch main https://github.com/GOU-GEE/deepseek-vision.git deepseek-vision-fresh`
   进入仓库后运行 `git status`，确认工作树干净且当前分支为 main。
2. 检查 Python 版本是否 >= 3.10（Mac/Linux 用 python3 --version；Windows 用
   python --version 或 py -V）。不满足时按平台安装：Mac 用 brew install python@3.12
   或到 python.org 下载；Windows 用 winget install Python.Python.3.12 或到
   python.org 下载（安装时勾选 Add python.exe to PATH）；Linux 用系统包管理器。
3. 创建全新的虚拟环境并安装运行依赖（按平台选一条）：
   - Mac/Linux:  `python3 -m venv .venv && .venv/bin/python -m pip install -e .`
   - Windows cmd: `python -m venv .venv && .venv\Scripts\python.exe -m pip install -e .`
   - Windows PowerShell: `py -3.12 -m venv .venv; .venv\Scripts\python.exe -m pip install -e .`
4. 配置 API Key：
   - 如果我在上面提供了智谱 Key，把它写入 `.env` 的 `VISION_API_KEY`，并确认：
     `VISION_MODEL=glm-4.6v-flash`、
     `VISION_BASE_URL=https://open.bigmodel.cn/api/paas/v4`。
   - 如果我明确提供的是硅基流动或通义千问 Key，必须同时使用该服务商对应的
     `VISION_MODEL` 与 `VISION_BASE_URL`，禁止把其他服务商 Key 配到智谱 Base URL。
   - 如果我没有提供 Key，**不要向我要明文 Key**：把 .env.example 复制为 .env，
     提示我只需填写 .env 中的 VISION_API_KEY 一个字段，我填好后你再继续。
     （付费 Key 不应明文发送给你，这样更安全。）
5. 用新虚拟环境的 Python 完整验收：
   - Mac/Linux：`.venv/bin/python scripts/verify_install.py`
   - Windows：`.venv\Scripts\python.exe scripts\verify_install.py`
   脚本必须依次通过：MCP stdio 握手、4 个工具注册、`vision_status`、一次真实视觉 API
   识图、同图同提示词第二次 `cached=true`。任一步失败都不能继续注册或声称成功。
6. 把 deepseek-vision 注册为 MCP 服务器：如果平台允许直接注册就注册，
   否则把下面的配置展示给用户手动填入平台设置：
{
  "mcp_servers": [
    {
      "name": "deepseek-vision",
      "command": "<第3步虚拟环境的python绝对路径：Mac/Linux 如 /path/to/.venv/bin/python，Windows 如 C:/path/to/.venv/Scripts/python.exe>",
      "args": ["-m", "deepseek_vision_mcp"],
      "env": {
        "VISION_API_KEY": "<第4步确定的Key；若用户选择自己填 .env 则此项可省略>",
        "VISION_MODEL": "glm-4.6v-flash",
        "VISION_BASE_URL": "https://open.bigmodel.cn/api/paas/v4"
      }
    }
  ]
}
   注意：VISION_API_KEY 未填时，Server 会自动读取 .env，不影响使用。
7. 加载技能：把仓库的 skills/ 目录加入我的技能搜索路径（重点是 skills/vision/SKILL.md）；
   如果平台不支持技能，把 SKILL.md 里的触发规则作为系统提示词的一部分。
8. Harness 终验：如果当前会话支持热加载，发送 `examples/test_image.jpg` 并确认主模型
   自动调用 `analyze_image`；如果不能热加载，明确提示用户重启或新建会话后发图终验。

执行约束：
- 每一步失败即停：展示完整错误信息与修复建议，不要跳过或假装成功。
- 修改任何配置文件都用 merge 合并，不要整文件覆盖；写完后校验 JSON 合法性。
- 本次是隔离的从零验收：不得复用旧仓库、旧 `.venv` 或旧 MCP command 路径；也不得
  删除或覆盖旧安装。
- 不要把 API Key 写进任何提交到仓库的文件（如 config.json 示例），只写本地 .env 或客户端配置。
- 完成后汇报：新安装路径、新 Python 绝对路径、MCP 配置位置、四段验收结果，以及是否
  需要重启 Harness 才能完成自动触发终验。
```

> 如果你更喜欢手动安装，请按下方 [快速开始](#快速开始) 操作，效果完全一样。

---

## 目录

- [一句话安装（复制给 AI 助手）](#-一句话安装复制给-ai-助手免手动操作)
- [解决的问题](#解决的问题)
- [工作原理](#工作原理)
- [支持的视觉模型](#支持的视觉模型)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [与 DeepSeek Harness 集成](#与-deepseek-harness-集成)
- [与 Codex 集成](#与-codex-集成)
- [Skill 自动触发机制](#skill-自动触发机制)
- [命令行工具](#命令行工具)
- [项目结构](#项目结构)
- [开发与测试](#开发与测试)
- [常见问题](#常见问题-faq)
- [隐私说明](#隐私说明)
- [许可证](#许可证)

---

## 解决的问题

| 场景 | 没有本项目的 DeepSeek | 有了本项目之后 |
| --- | --- | --- |
| 用户发来一张报错截图，问「哪里错了？」 | 模型看不到图，只能让用户贴文字 | 自动调用 `analyze_image`，识别报错内容并解答 |
| 用户问「这张照片是哪里？」 | 无法回答 | 视觉模型描述场景，DeepSeek 基于描述继续对话 |
| 用户上传图片要求提取文字 | 做不到 | 视觉模型做 OCR，返回文字 |
| 前端截图、UI 走查、图片差异对比 | 做不到 | 视觉模型描述界面元素与差异 |

一句话：**DeepSeek 负责「思考与对话」，视觉模型负责「看」**，MCP 负责把两者连起来。

---

## 工作原理

```
┌──────────────────────┐        ┌───────────────────────────────┐
│   DeepSeek 主模型     │        │   deepseek-vision-mcp (本仓库) │
│  (Harness / Codex)   │        │                               │
│                      │        │  ┌─────────────────────────┐  │
│  用户: "帮我看看       │  MCP   │  │  analyze_image 工具     │  │
│   ./a.png 有什么错误?"│ <────> │  │  - 路径 / URL / base64  │  │
│                      │ stdio  │  │  - 格式校验 / 压缩      │  │
│  Skill: vision       │        │  └───────────┬─────────────┘  │
│  自动触发工具调用      │        │              │ OpenAI 兼容     │
└──────────────────────┘        │              ▼                │
                                │  ┌────────────────────────────┐  │
                                │  │  视觉模型 API               │  │
                                │  │  智谱 GLM-4.6V /            │  │
                                │  │  硅基流动 Qwen2.5-VL /      │  │
                                │  │  通义千问 qwen-vl-plus      │  │
                                │  └────────────────────────────┘  │
                                └───────────────────────────────┘
```

调用流程：

1. 用户在 DeepSeek Harness / Codex 中发送图片路径、URL 或 base64 图片，
   并附带问题。
2. 主模型命中 `skills/vision/SKILL.md` 的触发条件，调用 MCP 工具
   `analyze_image(image=..., prompt=...)`。
3. MCP Server 加载图片（本地读取 / URL 下载 / base64 解码），校验格式与大小，
   必要时用 Pillow 压缩。
4. 将图片以 `data:image/...;base64,` 形式发给配置的视觉模型 API。
5. 视觉模型返回识别文本，MCP Server 包装为 JSON
   （`success / result / model / usage`）返回给主模型。
6. 主模型基于识别结果组织回答，用户无感。

---

## 支持的视觉模型

本项目实现的是 **OpenAI 兼容接口**（`/chat/completions` + `image_url` 内容块），
因此任何提供该接口的视觉模型都可以接入，只需改三个配置项：

| 服务商 | `VISION_BASE_URL` | `VISION_MODEL` | 说明 |
| --- | --- | --- | --- |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.6v-flash` | **免费，推荐**（GLM-4.6V 系列的免费版，当前免费视觉模型里效果最好） |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-VL-7B-Instruct` | 部分模型免费 |
| 通义千问 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-vl-plus` | 阿里云百炼 |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` | 免费层无需绑卡（AI Studio 获取 Key）；国内访问需代理 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` / `gpt-4o-mini` | 付费 |
| 其他兼容服务商 | 各自的 base URL | 各自的视觉模型名 | 任意 |

> 💡 **推荐：智谱 `glm-4.6v-flash`**——它是智谱最新视觉模型 GLM-4.6V 系列的免费版，
> 目前免费视觉模型里综合效果最好，也是本项目的默认配置。
> 官方文档：<https://docs.bigmodel.cn/cn/guide/models/free/glm-4.6v-flash>，
> 免费申请 Key：<https://open.bigmodel.cn>。

> 某些服务商有**特殊接口格式**（非 OpenAI 兼容）。本项目预留了扩展点：
> 继承 `providers/base.py` 中的 `BaseVisionProvider`，在
> `providers/__init__.py` 的 `build_provider()` 中注册，并通过
> `VISION_PROVIDER` 环境变量切换即可。当前版本内置 `openai_compatible`。

---

## 工具一览

MCP Server 提供 4 个工具：

| 工具 | 输入 | 用途 |
| --- | --- | --- |
| `analyze_image` | `image`（路径/URL/base64）+ `prompt`? + `task`? | 分析单张图片；`task` 提供 7 种预置任务（描述/OCR/UI/报错/图表/代码等），`prompt` 优先级更高 |
| `analyze_clipboard` | `prompt`? + `task`? | 读取系统剪贴板中的图片并分析（Win/macOS/Linux）——用户「截图即问」 |
| `compare_images` | `images`（2-4 张）+ `prompt`? | 多图对比分析，自动注入「共 N 张图，对比异同」指令 |
| `vision_status` | 无 | 返回配置与健康状态（版本/模型/Key 是否配置），用于诊断 |

`task` 预置任务：`describe`（默认，通用描述）、`ocr`（提取文字）、
`describe_ui`（UI 截图）、`diagnose_error`（报错诊断）、`understand_diagram`
（流程图/架构图）、`analyze_chart`（数据图表）、`code_from_screenshot`（代码截图）。

所有工具统一返回 JSON：`{"success": true/false, "result": "...", "model": "...",
"provider": "...", "fallback_used": true/false, "attempts": 0, "usage": {...},
"cached": true/false, "error": "..."}`。`cached: true` 表示命中
会话内缓存、未再次消耗视觉 API；失败时 `error` 字段给出错误码
（`CONFIG_ERROR` / `IMAGE_LOAD_FAILED` / `IMAGE_TOO_LARGE` / `VISION_API_ERROR` /
`CLIPBOARD_ERROR` / `INVALID_ARGUMENT` / `INTERNAL_ERROR`），`result` 附带可执行的
修复指引（如 401 → 检查 Key、429 → 稍后重试），主模型可直接转述给用户。

---

## 快速开始

### 1. 申请 API Key（以智谱 AI 为例，约 2 分钟）

1. 打开 <https://open.bigmodel.cn>，注册并登录。
2. 进入「API Keys」页面，创建一个 API Key（形如 `xxxxxxxx.xxxxxxxx`）。
3. 智谱的 `glm-4.6v-flash`（GLM-4.6V 免费版，当前免费视觉模型里效果最好）提供免费额度，无需充值即可体验。
4. 想用其他服务商，到对应控制台申请 Key 即可（见上表）。

### 2. 安装

要求 **Python 3.10+**。还没装的话，按你的系统选一种方式：

| 系统 | 安装 Python 3.10+ |
| --- | --- |
| macOS | `brew install python@3.12`，或从 <https://www.python.org/downloads/macos/> 下载安装包 |
| Windows | `winget install Python.Python.3.12`，或从 <https://www.python.org/downloads/windows/> 下载安装包（安装时**勾选 "Add python.exe to PATH"**） |
| Linux | Debian/Ubuntu：`sudo apt install python3.12 python3.12-venv`；其他发行版用各自的包管理器 |

> Windows 提示 `python` 找不到时，试试 `py -3.12`（Python 启动器，装 python.org 版本自带）。

然后克隆并安装（命令按你的系统选）：

```bash
git clone https://github.com/GOU-GEE/deepseek-vision.git
cd deepseek-vision

# ── 创建虚拟环境并激活 ──────────────────────────────
# Mac / Linux:
python3 -m venv .venv
source .venv/bin/activate

# Windows (cmd 命令提示符):
# python -m venv .venv
# .venv\Scripts\activate

# Windows (PowerShell):
# py -3.12 -m venv .venv
# .venv\Scripts\Activate.ps1

# ── 安装（含开发依赖，用于跑测试；三平台命令相同）──
pip install -e ".[dev]"
```

### 3. 配置

```bash
cp .env.example .env        # Mac / Linux
# Windows (cmd):      copy .env.example .env
# Windows (PowerShell): Copy-Item .env.example .env
```

编辑 `.env`，填入你的 API Key（至少修改 `VISION_API_KEY`，其他可用默认值）：

```bash
VISION_API_KEY=你的智谱APIKey
VISION_MODEL=glm-4.6v-flash
VISION_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

也可以改用 `config.json`（参考 `config.example.json`）：

```bash
cp config.example.json config.json
# Windows 同样用 copy / Copy-Item
# 然后编辑 config.json 填入 api_key
```

配置读取优先级：**环境变量 > `.env` 文件 > `config.json` > 默认值**。

### 4. 校验配置

```bash
deepseek-vision-mcp --check
# 或
python -m deepseek_vision_mcp --check
```

看到 `[OK] 配置就绪` 即配置正确。

### 5. 本地自测（不经过 MCP，直接识别一张图）

```bash
deepseek-vision-mcp --test-image examples/test_image.jpg
```

正常会打印视觉模型返回的识别结果 JSON。

### 6. 启动 MCP Server

```bash
deepseek-vision-mcp
# 或
python -m deepseek_vision_mcp
```

Server 通过 **stdio** 与客户端通信，单独运行时没有输出是正常的——
等待 MCP 客户端连接。接下来把它注册到 Harness / Codex 即可。

### 7. 运行测试

```bash
pytest -v
```

---

## 配置说明

### 环境变量一览

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `VISION_API_KEY` | ✅ | 无 | 视觉模型 API Key |
| `VISION_API_KEYS` | | 无 | 多 Key，逗号分隔；429/401/403 时自动轮换，优先于单 Key |
| `VISION_MODEL` | | `glm-4.6v-flash` | 视觉模型名称（默认推荐智谱免费版） |
| `VISION_MODELS` | | 无 | 同一服务商下的模型降级链，逗号分隔 |
| `VISION_FALLBACKS_JSON` | | `[]` | 跨服务商备用链（JSON，不含 Key；用 `api_key_env` 引用凭据环境变量） |
| `VISION_FALLBACK_API_KEY` | | 无 | DSH 可视化备用服务使用的独立 Key |
| `VISION_MAX_ATTEMPTS` | | `4` | 单次工具调用的真实视觉 API 请求总预算（1-12） |
| `VISION_CIRCUIT_COOLDOWN_SECONDS` | | `90` | 429/5xx 端点的短期熔断秒数（5-3600） |
| `VISION_BASE_URL` | | `https://open.bigmodel.cn/api/paas/v4` | OpenAI 兼容 API 基础 URL |
| `VISION_MAX_IMAGE_SIZE_KB` | | `2048` | 图片大小限制（KB），超限自动压缩 |
| `VISION_TIMEOUT_SECONDS` | | `60` | 调用视觉模型 API 的超时（秒） |
| `VISION_TEMPERATURE` | | `0.3` | 采样温度（0-2），0.3 更适合 OCR/报错诊断 |
| `VISION_DOWNLOAD_TIMEOUT_SECONDS` | | `30` | 下载 URL 图片的超时（秒） |
| `VISION_ALLOW_PRIVATE_IMAGE_URLS` | | `false` | 是否允许下载内网 URL（SSRF 防护，自建内网服务时设为 `true`） |
| `VISION_ALLOWED_FORMATS` | | `jpg,jpeg,png,webp` | 允许的图片格式 |
| `VISION_USE_CONFIG_FILE` | | `true` | 是否读取 `config.json` |
| `VISION_CONFIG_FILE` | | `./config.json` | `config.json` 的路径 |
| `VISION_PROVIDER` | | `openai_compatible` | 提供商类型（预留扩展） |
| `VISION_CACHE_ENABLED` | | `true` | 是否启用会话内识别结果缓存（不落盘） |
| `VISION_CACHE_MAX_ENTRIES` | | `128` | 缓存最多保留的结果数（LRU） |
| `VISION_CACHE_TTL_SECONDS` | | `3600` | 缓存有效期（秒） |

### config.json 格式

```json
{
  "vision": {
    "api_key": "your-api-key",
    "api_keys": ["备用-key-1", "备用-key-2"],
    "model": "glm-4.6v-flash",
    "models": ["glm-4.6v-flash", "glm-4v-flash"],
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "max_image_size_kb": 2048,
    "timeout_seconds": 60
  }
}
```

键名大小写不敏感（`api_key` 与 `API_KEY` 等价），也可以直接写扁平形式
（`VISION_API_KEY`）。环境变量 / `.env` 始终优先于 `config.json`。

跨服务商备用示例（Key 不写进 JSON）：

```bash
VISION_FALLBACK_API_KEY='你的硅基流动Key'
VISION_FALLBACKS_JSON='[{"id":"siliconflow","model":"Qwen/Qwen2.5-VL-7B-Instruct","base_url":"https://api.siliconflow.cn/v1","api_key_env":"VISION_FALLBACK_API_KEY"}]'
```

### 切换服务商示例

**切到硅基流动：**

```bash
VISION_API_KEY=sk-硅基流动的Key
VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
VISION_BASE_URL=https://api.siliconflow.cn/v1
```

**切到通义千问：**

```bash
VISION_API_KEY=sk-通义千问的Key
VISION_MODEL=qwen-vl-plus
VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

## 与 DeepSeek Harness 集成

DeepSeek Harness（2026-08-13 发布，目前处于 Developer Preview）原生支持 **MCP 服务器**（内置
`@deepseek-ai/dsh-mcp-client` 插件），也支持 **Skill 目录**（内置
`@deepseek-ai/dsh-skill-filesystem`）。本项目两者兼备：MCP Server 提供
`analyze_image` 等 4 个工具，`skills/vision/SKILL.md` 负责自动触发。
推荐以下两种方式之一。

### 方式一（推荐）：安装 DSH Bundle

```bash
export VISION_API_KEY='你的智谱APIKey'
npx -y @deepseek-ai/dsh@0.1.0-rc.6 plugin --profile web add dsh-plugin-deepseek-vision@0.4.1
npx -y @deepseek-ai/dsh@0.1.0-rc.6 web
```

插件首次启动时会在 `$DSH_HOME/cache` 自动准备隔离 Python 环境并启动 MCP，
无需克隆本仓库、手工建立虚拟环境、修改 Python 绝对路径或复制 Skill。选择文本版
DeepSeek 后可直接粘贴或拖入图片：插件把图片安全保存为临时文件，并在输入框上方显示
缩略图卡带，输入框内只保留一个隐藏的图片引用标记，不展示工具调用长指令。
桌面运行直接复用 DSH App 内置 Node，不依赖 GUI 的 PATH，也不要求
用户另装 Node；如果系统没有 Python 3.10+，插件会下载经过固定 SHA-256 校验的官方
`uv` 引导器，在 `$DSH_HOME/cache` 自动准备隔离 CPython 3.12 和运行环境。

#### 粘贴图片后的输入框交互

- **缩略图卡带**：粘贴或拖入图片后，输入框上方显示缩略图卡带，宽度按 DSH composer
  变量收敛，不超过输入框宽度；上传中 / 已就绪 / 失败均有状态提示。
- **指令不占输入框**：输入框内只显示一个隐藏的 `🖼️` 引用标记，不显示
  `请调用 mcp__deepseek-vision__…` 长文本。
- **无文字发送**：用户没有输入任何要求就直接发送时，引用自动展开为预设指令——
  单图调用 `analyze_image`，多图调用 `compare_images`。
- **有文字发送**：用户已输入自己的问题（如“这是什么动物？”）时，只传递图片路径，
  不注入预设指令，模型按用户的问题选择工具与任务。
- **发送后自动清理**：消息发送成功后缩略图卡带自动关闭并释放本地预览；发送未成功时
  图片不丢失——引用序列化失败时缩略图与引用保留可重试，host 层失败时 DSH 会把
  序列化文本（含图片路径）恢复回输入框。
- **手动移除**：点击缩略图右上角 × 可移除该图片，并同步撤销输入框内的引用；
  多图移除一张后自动重建剩余图片的指令。

> **安装耗时预期**：正式 npm Bundle 的普通安装目标是 1-3 分钟；系统缺少可用
> Python 时，首次下载隔离 CPython 可能再花 2-8 分钟，之后复用缓存。README 顶部的
> “一会话从零部署并验收”还包含克隆源码、构建、全套测试、备份、真实 API 与桌面 UI
> 验收，15-30 分钟属于发布审计耗时，不代表普通用户每次安装都要这么久。

#### macOS 桌面版可视化配置

安装 Bundle 并重新打开 DeepSeek Harness 后，进入：

```text
设置 → 插件 → 插件配置 → DeepSeek Vision
```

选择视觉服务商后会自动带入推荐模型和 Base URL；还可以启用独立的备用服务商和备用
Key。主服务持续遇到 429/5xx 时，插件在全局请求预算内自动退避并切换备用服务，随后
对故障端点短暂熔断，避免请求风暴。填写 API Key 后可直接“保存”并分别测试主、备用
连接。测试会发送一张 1×1 图片并请求最多 8 tokens，因此会产生一次极小的真实
视觉请求。Key 由 DSH 官方凭据存储保存，页面和普通配置只显示“已配置”，不会回显原文；
非本机 Base URL 必须使用 HTTPS，且不能在 URL 中夹带账号密码。保存后用 `Cmd+Q` 完全
退出并重新打开桌面版，使正在运行的 MCP 进程读取新配置。主、备用 Key 分别进入 DSH
官方凭据存储；普通配置只保存服务商、模型、Base URL 和优先级。

当前已在官方 macOS 桌面版内置的 DSH `0.1.0-rc.5` 实机验证，并在 CI 验证 npm
公开版本 `0.1.0-rc.6` 的干净 profile 安装（官方未向 npm 发布 `rc.5`，因此 CI 无法
在线安装该版本）。DSH 仍处于预览期，升级后应重新执行一次连接和图片验收。

> 包内自带完整说明与等效的手写配置（`plugins/dsh-plugin-deepseek-vision/README.md`）。
> 本包采用 bundle patch 形态并使用 DSH 内置 `dsh-mcp-client`。当前 npm 版本发布前，
> 请从仓库构建 tarball 做本地验收；不要把尚未发布的命令描述成已可公开安装。

### 方式二：手写 cordis.patch.yml（不装插件，等效）

在 profile 的 `cordis.patch.yml` 中加入一个 `dsh-mcp-client` 插件实例：

```yaml
- insert:
    - id: deepseek-vision
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: deepseek-vision
        transport: stdio
        command: /abs/path/to/deepseek-vision/.venv/bin/python
        args: ['-m', 'deepseek_vision_mcp']
        env:
          VISION_API_KEY: !!js process.env.VISION_API_KEY
          VISION_MODEL: glm-4.6v-flash
          VISION_BASE_URL: https://open.bigmodel.cn/api/paas/v4
```

工具将以 `mcp__deepseek-vision__analyze_image`、
`mcp__deepseek-vision__analyze_clipboard`、
`mcp__deepseek-vision__compare_images`、
`mcp__deepseek-vision__vision_status` 的名字暴露给模型（与 Claude Code /
Codex 相同的 server 限定命名）。`command` 必须使用虚拟环境 Python 的
绝对路径；API Key 走 DSH 环境变量或项目 `.env` 均可。

### 加载 Skill（自动触发）

DSH 通过 `dsh-skill-filesystem` 扫描 `~/.dsh/skills/`（`$DSH_HOME/skills`），
把本仓库的 Skill 复制进去即可（DSH 自动热加载，无需重启）：

```bash
mkdir -p ~/.dsh/skills && cp -r skills/vision ~/.dsh/skills/
```

加载后，用户发送图片/路径/URL、粘贴截图、或要求「看图/OCR/对比图片」时，
模型命中 `vision` Skill 自动调用工具。

### 不支持 Skill 时——通过系统提示词手动触发

把以下内容追加到系统提示词中即可获得同样的自动触发效果：

```text
当用户发送图片路径、图片 URL、base64 图片，或要求识别/理解/描述图片内容时，
你必须调用 MCP 工具 analyze_image(image="<图片输入>", prompt="<针对用户问题的任务描述>")，
并根据工具返回的 result 字段回答用户。不要编造图片内容。
```

### 插件生态说明（能否作为插件发布 / 是否需要审核）

- **DSH Bundle 是普通 npm 包**：本包通过清单中的 `dsh.bundle.patch` 组合宿主插件、
  DSH 内置 MCP client 和浏览器客户端模块。官方发布文档见
  <https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md>。
- **公开安装路径不要求提交官方商店审核**：作者可发布公开 npm 包，用户也可从 npm、
  GitHub 或本地 tarball 安装。官方当前建议用 GitHub 的 `dsh-plugin` topic 做发现；
  这不代表 DeepSeek 官方背书或安全审核。
- **Developer Preview 注意**：当前测试 `0.1.0-rc.5` 与 `0.1.0-rc.6`；DSH 在 0.2.0 前可能发生
  破坏性变化。每次发布都必须用干净 profile 执行安装、`--dump-config` 和真实图片验收。

### 验证集成

在 Harness 里给 DeepSeek 发一条消息：

```text
帮我看看 examples/test_image.jpg 里画了什么？
```

如果配置正确，你应该看到模型先调用 `analyze_image` 工具，再基于返回结果回答。
也可以直接问「看看我刚复制的截图」测试剪贴板工具（`analyze_clipboard`）。

粘贴/拖拽图片时按下面顺序检查输入框行为：

1. 输入框上方出现缩略图卡带，宽度不超过输入框；
2. 输入框内只有 `🖼️` 引用标记，没有 `请调用 mcp__deepseek-vision__…` 长文本；
3. 不输入文字直接发送 → 自动调用 `analyze_image`（多图 `compare_images`）；
4. 输入自己的问题再发送 → 只按你的问题分析，不注入预设指令；
5. 发送成功后缩略图卡带自动关闭；发送未成功时图片不丢失（缩略图或路径保留）。

---

## 与 DSH 原生视觉 / 其他视觉插件的区别

社区里已有不少「给 DeepSeek 加眼睛」的方案（vision bridge / MCP 桥 /
内置视觉路由等），本项目定位如下，方便你按需选择：

| 维度 | 本项目（deepseek-vision-mcp） | 常见其他方案 |
| --- | --- | --- |
| **主模型** | **不替换 DeepSeek 主模型**——对话、思考、工具调用仍全部由 DeepSeek 完成 | 部分方案是替换主模型或包装成独立 agent |
| **视觉模型的角色** | **纯辅助工具**：只在需要时把图片转成文字喂回 DeepSeek，不参与决策 | 部分方案把视觉能力做成「主路由」干预对话流程 |
| **默认模型** | **智谱免费 `glm-4.6v-flash`**（当前免费视觉模型里效果最好），开箱即用 | 部分方案默认付费模型或需要自行找免费路由 |
| **配置方式** | **DSH 可视化配置页**（设置 → 插件 → DeepSeek Vision）：多服务商、主/备用 Key、独立测试，无需改文件 | 多为手写 cordis.yml / 环境变量 |
| **DSH 输入体验** | 缩略图卡带不超输入框、指令不显示在输入框；无文字自动预设指令，有文字只传图片路径，发送后自动清理 | 常把长指令直接写入输入框 |
| **缓存与限流容错** | 内置 LRU 结果缓存（同图秒回 `cached=true`）+ 多 Key 轮换 + 模型降级 + 429 指数退避 + 熔断 | 部分方案无缓存、429 直接失败 |
| **运行方式** | 独立 MCP Server（Python wheel 内置于插件，自动引导 Python 运行时），任意 MCP 客户端可用 | 多为纯 JS 插件，仅限 DSH 内使用 |
| **Key 安全** | Key 存 DSH 官方凭据存储，不落库、不入日志、不进模型上下文 | 部分方案 Key 明文存配置文件 |

**一句话总结**：DeepSeek 负责「思考与对话」，本项目只负责在需要时替它「看一眼」——
免费、可配置、扛限流，且不改变你的主模型与既有工作流。

---

## 与 Codex 集成

Codex 同样通过 MCP 注册服务器。在其配置文件（如 `~/.codex/config.toml`）中：

```toml
[mcp_servers.deepseek-vision]
command = "python"
args = ["-m", "deepseek_vision_mcp"]
env = { VISION_API_KEY = "your-api-key", VISION_MODEL = "glm-4.6v-flash", VISION_BASE_URL = "https://open.bigmodel.cn/api/paas/v4" }
```

Skill 目录加载方式与 Harness 相同（方式二 / 方式三）。

---

## Skill 自动触发机制

`skills/vision/SKILL.md` 是标准的 Agent Skill 定义（YAML frontmatter + Markdown 正文），
包含：

- **触发条件**：本地图片路径 / 图片 URL / base64 图片 / 用户要求识别、提取文字、
  描述图片 / 用户上传了图片但模型无法直接处理。
- **必须执行的操作**：调用 `analyze_image`，并给出了根据用户问题构造 `prompt`
  的规则（提取文字、找错误、描述场景、识别界面元素等）。
- **示例对话**：如「帮我看看 ./screenshot.png 里有什么错误？」→ 调用工具 → 返回结果。

### 手动触发（供调试）

在支持 MCP 的客户端里，直接让主模型调用工具：

```text
请调用 analyze_image 工具分析 ./screenshot.png，
prompt 设为"请识别图片中的错误信息，并说明可能的原因"。
```

也可以在命令行用 `--test-image` 直接体验（不经过主模型）：

```bash
deepseek-vision-mcp --test-image ./screenshot.png --prompt "请识别图片中的错误信息"
```

---

## 命令行工具

```bash
deepseek-vision-mcp                    # 以 stdio 启动 MCP Server（默认）
deepseek-vision-mcp --check            # 校验配置
deepseek-vision-mcp --test-image PATH  # 直接识别一张图（本地自测）
deepseek-vision-mcp --test-image URL --prompt "提取文字"
```

---

## 项目结构

```
deepseek-vision-mcp/
├── README.md
├── LICENSE                     # MIT
├── pyproject.toml
├── config.example.json
├── .env.example
├── src/
│   └── deepseek_vision_mcp/
│       ├── __init__.py
│       ├── server.py           # MCP Server 入口：analyze_image / analyze_clipboard / compare_images / vision_status
│       ├── config.py           # 配置加载（.env / 环境变量 / config.json）
│       ├── cache.py            # 会话内 TTL/LRU 结果缓存（不保存图片）
│       ├── image_utils.py      # 图片加载、编码、校验、压缩、SSRF 防护
│       ├── clipboard.py        # 跨平台剪贴板图片读取（Win/macOS/Linux）
│       ├── prompts.py          # 预置任务提示词（OCR/UI/报错/图表等 7 种）
│       ├── providers/
│       │   ├── __init__.py     # build_provider 分发
│       │   ├── base.py         # 视觉模型抽象基类（扩展点）
│       │   ├── openai_compatible.py  # OpenAI 兼容实现（多 Key/模型降级/重试）
│       │   └── router.py       # 跨服务商备用链、全局预算与短期熔断
│       ├── main.py             # 命令行入口（--check / --check-clipboard / --test-image）
│       └── __main__.py
├── skills/
│   └── vision/
│       └── SKILL.md            # vision Skill 定义
├── examples/
│   ├── test_image.jpg          # 测试图片
│   ├── sample_chat.md          # 示例对话
│   ├── opencode.json           # OpenCode 集成配置示例
│   ├── claude_code_settings.json  # Claude Code 集成配置示例
│   └── codex_config.toml       # Codex 集成配置示例
├── scripts/
│   ├── install.sh
│   ├── test_mcp.sh             # Mac/Linux 完整验收包装脚本
│   └── verify_install.py       # 跨平台 MCP + 真实 API + 缓存验收
├── plugins/
│   └── dsh-plugin-deepseek-vision/  # DSH Bundle（缩略图卡带 + 隐藏指令引用 + 托管 Python runtime）
├── docs/                       # 项目交接日志 / 发布流程 / 对比测试 / 截图
├── tests/                      # pytest 测试（94 个用例）
├── SECURITY.md                # 漏洞报告方式与发布安全清单
└── .github/workflows/         # Python/Node/官方 DSH 安装测试与 PyPI/npm 发布
```

---

## 开发与测试

> 📋 维护者/新开发者请先读 **`docs/PROJECT_LOG.md`**（项目交接日志：环境、命令、坑、待办）；
> 发布流程见 `docs/RELEASING.md`，对比测试见 `docs/BENCHMARK.md`。

```bash
pip install -e ".[dev]"
pytest -v
```

测试覆盖：本地图片 / URL / base64 三种输入、无效 API Key、文件不存在、
图片超限压缩、流式下载上限、SSRF、多 Key 轮换、模型降级、会话缓存、
多提供商切换、配置优先级等。测试全部 mock 掉
外部 API，**不需要真实 Key 即可运行**。

---

## 常见问题 (FAQ)

**Q：报错 `缺少 VISION_API_KEY`？**
A：没有配置 API Key。复制 `.env.example` 为 `.env` 并填入 Key，或用
`deepseek-vision-mcp --check` 定位问题。

**Q：调用工具返回 `VISION_API_ERROR`？**
A：视觉模型 API 调用失败。常见原因：Key 无效、`VISION_BASE_URL` 写错、
模型名不存在、余额不足、网络超时。按工具返回的 `result` 中的提示排查。

**Q：免费 API 经常 429 怎么办？**
A：DSH 用户可在可视化设置中启用另一家备用服务商；主服务持续 429 时会在全局
请求预算内自动退避、切换并短暂熔断故障端点。命令行用户可用
`VISION_API_KEYS` / `VISION_MODELS` 配置同服务商降级，或用上面的
`VISION_FALLBACKS_JSON` 配置跨服务商备用链。请只使用自己合法持有的 Key，遵守
服务商限流和使用条款。

**Q：缓存会保存我的图片吗？**
A：不会。默认缓存仅在 MCP Server 进程内存中保存图片内容的 SHA256 哈希与识别文本，
不保存图片、不落盘，进程退出即清空；可设置 `VISION_CACHE_ENABLED=false` 关闭。

**Q：返回 `IMAGE_LOAD_FAILED`？**
A：图片加载失败。检查本地路径是否存在、URL 是否可访问（带 `http(s)://`）、
base64 是否完整。工具会返回具体原因。

**Q：返回 `IMAGE_TOO_LARGE`？**
A：图片压缩后仍超过 `VISION_MAX_IMAGE_SIZE_KB`。换更小的图片，或调大限制。

**Q：支持哪些图片格式？**
A：`jpg / jpeg / png / webp`，可用 `VISION_ALLOWED_FORMATS` 调整。
其他格式会先尝试用 Pillow 识别。

**Q：怎么分析剪贴板里的截图？**
A：直接问主模型「看看我刚复制的截图」即可——它命中 Skill 后会调用
`analyze_clipboard` 工具读取系统剪贴板。也可先手动验证：
`deepseek-vision-mcp --check-clipboard`（无需 API Key）。

**Q：能对比多张图片吗？**
A：可以。让主模型调用 `compare_images` 工具，传入 2-4 张图片的
路径/URL（如「对比 design_v1.png 和 design_v2.png 有什么不同」）。

**Q：为什么下载内网图片 URL 会报错？**
A：出于安全考虑（SSRF 防护），默认拒绝解析到内网/保留地址的 URL，
防止恶意链接探测内网服务或云元数据。自建内网图片服务时，可设置
`VISION_ALLOW_PRIVATE_IMAGE_URLS=true` 显式放行。

**Q：输出被截断或返回空内容怎么办？**
A：Server 已内置处理：输出被 `max_tokens` 截断会自动升档重试；
若模型只返回思考内容（reasoning_content），会提示更换非推理模型。
仍失败时可按 `VISION_API_ERROR` 的 result 提示排查。

**Q：图片会被压缩吗？**
A：超过大小限制时自动压缩（先降质量，再缩分辨率），不影响识别结果。

**Q：Windows 上怎么运行？**
A：与 Mac/Linux 只有两处命令差异，其余（`deepseek-vision-mcp`、`pytest` 等）完全一致：
- **激活虚拟环境**：cmd 用 `.venv\Scripts\activate`，PowerShell 用 `.venv\Scripts\Activate.ps1`；
- **复制配置文件**：cmd 用 `copy .env.example .env`，PowerShell 用 `Copy-Item .env.example .env`；
- 注册 MCP 服务器时 `command` 填虚拟环境 Python 绝对路径：
  `C:/path/to/.venv/Scripts/python.exe`（正斜杠写法，避免 JSON 转义）。
另外 `scripts/install.sh` 是 bash 脚本，仅适用于 Mac/Linux；Windows 用户请直接按
上方 [快速开始](#快速开始) 的 Windows 命令操作，效果相同。

**Q：能用免费模型吗？**
A：可以。智谱 `glm-4.6v-flash`（当前免费视觉模型里效果最好）与硅基流动部分模型提供免费额度，
只需申请 Key 即可，本项目代码本身无需付费。

---

## 隐私说明

- 使用本项目时，**图片内容会被发送到你所配置的第三方视觉模型 API**
  （智谱 AI / 硅基流动 / 通义千问 / OpenAI 等），请勿传入敏感或涉密图片；
  剪贴板截图可能包含 token/凭据，分析后临时文件会被立即删除。
- API Key 只保存在你的本机（`.env` / `config.json` / 环境变量），
  项目代码**不内置、不收集、不上传**任何 Key。
- **安全防护**：URL 图片下载默认启用 SSRF 防护（拒绝内网/保留地址、
  每跳重定向重新校验、限制重定向次数与下载大小），防止恶意链接探测
  内网服务或云元数据。
- 请求内容（图片 + prompt）由对应服务商的隐私政策约束，
  建议查阅各服务商的隐私条款。
- 若对隐私有严格要求，可选择自建 OpenAI 兼容的视觉推理服务（如 vLLM
  部署 Qwen-VL），把 `VISION_BASE_URL` 指向内网地址。

---

## 许可证

[MIT](./LICENSE)
