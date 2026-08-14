# deepseek-vision-mcp

给 **DeepSeek（及其他纯文本大模型）装上「眼睛」** 的开源 MCP Server。

DeepSeek 系列模型是纯文本模型，无法直接识别图片。本项目的思路是：
通过 **MCP Server 暴露一个 `analyze_image` 工具**，把图片交给第三方
**OpenAI 兼容的视觉模型 API**（智谱 GLM-4V、硅基流动 Qwen2.5-VL、
通义千问 qwen-vl-plus 等）识别，再把识别文本返回给主模型。
配合项目自带的 **Skill 文件**，DeepSeek 主模型在遇到图片时会**自动**调用
该工具——对用户来说，就像 DeepSeek 突然会「看图」了。

> 视觉识别能力由第三方模型提供，图片会被发送到对应服务商的 API。
> 请阅读文末的[隐私说明](#隐私说明)。

---

## 🚀 一句话安装（复制给 AI 助手，免手动操作）

在 DeepSeek Harness / Codex 等智能体平台中，**把下面整段话复制发给你的 AI 助手**，
它会自动完成：克隆仓库 → 检查并准备 Python 环境 → 安装依赖 → 让你填写 API Key →
注册 MCP 服务器 → 加载 Skill → 自测图片识别。全程无需你手动敲命令。

```text
请帮我安装并启用 deepseek-vision-mcp（GitHub: https://github.com/GOU-GEE/deepseek-vision），
它通过 MCP 工具 analyze_image 让纯文本模型具备图片识别能力。请按以下步骤自动完成：

1. 克隆仓库到当前目录（已存在则跳过）：git clone https://github.com/GOU-GEE/deepseek-vision.git
2. 检查 python3 版本是否 >= 3.10；不满足时用 brew install python@3.12（Mac）
   或提示用户手动安装（Windows）。
3. 创建虚拟环境并安装依赖：
   python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
4. 配置 API Key：把 .env.example 复制为 .env，然后向用户索要视觉模型 API Key
   （默认智谱 glm-4v-flash，可到 https://open.bigmodel.cn 免费申请；
   也支持硅基流动 / 通义千问，只需改 VISION_MODEL 与 VISION_BASE_URL），
   把 Key 填入 .env 的 VISION_API_KEY。
5. 校验配置：运行 deepseek-vision-mcp --check，确认显示 [OK] 配置就绪。
6. 把 deepseek-vision 注册为 MCP 服务器：如果平台允许直接注册就注册，
   否则把下面的配置展示给用户手动填入平台设置：
{
  "mcp_servers": [
    {
      "name": "deepseek-vision",
      "command": "<第3步虚拟环境的python绝对路径，如 /path/to/.venv/bin/python>",
      "args": ["-m", "deepseek_vision_mcp"],
      "env": {
        "VISION_API_KEY": "<用户的Key>",
        "VISION_MODEL": "glm-4v-flash",
        "VISION_BASE_URL": "https://open.bigmodel.cn/api/paas/v4"
      }
    }
  ]
}
7. 加载技能：把仓库的 skills/ 目录加入我的技能搜索路径（重点是 skills/vision/SKILL.md）；
   如果平台不支持技能，把 SKILL.md 里的触发规则作为系统提示词的一部分。
8. 验证：用 examples/test_image.jpg 实际调用一次 analyze_image 工具，
   确认能返回图片内容。若注册后当前会话还无法调用该工具，提示用户重启会话。

完成后向用户汇报每一步的结果。
```

**更短的极简版**（如果助手足够聪明，这段也够用）：

```text
请帮我安装并启用 https://github.com/GOU-GEE/deepseek-vision 项目，让我的 DeepSeek
能识别图片：克隆仓库 → 建 .venv 虚拟环境 → pip install -e ".[dev]" → 复制 .env.example
为 .env 并让我填 VISION_API_KEY（默认智谱 glm-4v-flash）→ deepseek-vision-mcp --check
校验 → 把它注册为 MCP 服务器（command 用 .venv 的 python 绝对路径，args 为
["-m","deepseek_vision_mcp"]，env 配 VISION_API_KEY / VISION_MODEL / VISION_BASE_URL）→
加载 skills/ 目录 → 最后用 examples/test_image.jpg 自测 analyze_image 工具，并汇报结果。
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
                                │  ┌─────────────────────────┐  │
                                │  │  视觉模型 API            │  │
                                │  │  智谱 GLM-4V /           │  │
                                │  │  硅基流动 Qwen2.5-VL /   │  │
                                │  │  通义千问 qwen-vl-plus   │  │
                                │  └─────────────────────────┘  │
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
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4v-flash` | 有免费额度，默认配置 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-VL-7B-Instruct` | 部分模型免费 |
| 通义千问 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-vl-plus` | 阿里云百炼 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` / `gpt-4o-mini` | 付费 |
| 其他兼容服务商 | 各自的 base URL | 各自的视觉模型名 | 任意 |

> 某些服务商有**特殊接口格式**（非 OpenAI 兼容）。本项目预留了扩展点：
> 继承 `providers/base.py` 中的 `BaseVisionProvider`，在
> `providers/__init__.py` 的 `build_provider()` 中注册，并通过
> `VISION_PROVIDER` 环境变量切换即可。当前版本内置 `openai_compatible`。

---

## 快速开始

### 1. 申请 API Key（以智谱 AI 为例，约 2 分钟）

1. 打开 <https://open.bigmodel.cn>，注册并登录。
2. 进入「API Keys」页面，创建一个 API Key（形如 `xxxxxxxx.xxxxxxxx`）。
3. 智谱的 `glm-4v-flash` 提供免费额度，无需充值即可体验。
4. 想用其他服务商，到对应控制台申请 Key 即可（见上表）。

### 2. 安装

要求 **Python 3.10+**。

```bash
git clone https://github.com/GOU-GEE/deepseek-vision.git
cd deepseek-vision-mcp

# 推荐：创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 以可编辑模式安装（含开发依赖，用于跑测试）
pip install -e ".[dev]"
```

### 3. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key（至少修改 `VISION_API_KEY`，其他可用默认值）：

```bash
VISION_API_KEY=你的智谱APIKey
VISION_MODEL=glm-4v-flash
VISION_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

也可以改用 `config.json`（参考 `config.example.json`）：

```bash
cp config.example.json config.json
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
| `VISION_MODEL` | | `glm-4v-flash` | 视觉模型名称 |
| `VISION_BASE_URL` | | `https://open.bigmodel.cn/api/paas/v4` | OpenAI 兼容 API 基础 URL |
| `VISION_MAX_IMAGE_SIZE_KB` | | `2048` | 图片大小限制（KB），超限自动压缩 |
| `VISION_TIMEOUT_SECONDS` | | `60` | 调用视觉模型 API 的超时（秒） |
| `VISION_DOWNLOAD_TIMEOUT_SECONDS` | | `30` | 下载 URL 图片的超时（秒） |
| `VISION_ALLOWED_FORMATS` | | `jpg,jpeg,png,webp` | 允许的图片格式 |
| `VISION_USE_CONFIG_FILE` | | `true` | 是否读取 `config.json` |
| `VISION_CONFIG_FILE` | | `./config.json` | `config.json` 的路径 |
| `VISION_PROVIDER` | | `openai_compatible` | 提供商类型（预留扩展） |

### config.json 格式

```json
{
  "vision": {
    "api_key": "your-api-key",
    "model": "glm-4v-flash",
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "max_image_size_kb": 2048,
    "timeout_seconds": 60
  }
}
```

键名大小写不敏感（`api_key` 与 `API_KEY` 等价），也可以直接写扁平形式
（`VISION_API_KEY`）。环境变量 / `.env` 始终优先于 `config.json`。

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

DeepSeek Harness（以及其他支持 MCP 的智能体平台）通过「MCP 服务器配置 +
Skill 目录」两个入口接入本项目。

### 方式一：在 Harness 中注册 MCP Server

在 Harness 的配置文件中加入：

```json
{
  "mcp_servers": [
    {
      "name": "deepseek-vision",
      "command": "python",
      "args": ["-m", "deepseek_vision_mcp"],
      "env": {
        "VISION_API_KEY": "your-api-key",
        "VISION_MODEL": "glm-4v-flash",
        "VISION_BASE_URL": "https://open.bigmodel.cn/api/paas/v4"
      }
    }
  ]
}
```

> 如果你的 `python` 不在 PATH 中，请换成绝对路径（如 `/path/to/.venv/bin/python`）。
> 建议使用虚拟环境中的 Python，确保安装了本项目的依赖。

### 方式二：加载 Skill 目录

将本仓库的 `skills/` 目录加入 Harness 的 Skill 搜索路径（或把
`skills/vision/SKILL.md` 复制到 Harness 的 skills 目录）。加载后，
主模型在遇到图片时会自动触发 `vision` Skill，进而调用 `analyze_image` 工具。

### 方式三：不支持 Skill 时——通过系统提示词手动触发

如果你的 Harness 版本不支持 Skill，把以下内容追加到系统提示词中即可获得
同样的自动触发效果：

```text
当用户发送图片路径、图片 URL、base64 图片，或要求识别/理解/描述图片内容时，
你必须调用 MCP 工具 analyze_image(image="<图片输入>", prompt="<针对用户问题的任务描述>")，
并根据工具返回的 result 字段回答用户。不要编造图片内容。
```

### 验证集成

在 Harness 里给 DeepSeek 发一条消息：

```text
帮我看看 examples/test_image.jpg 里画了什么？
```

如果配置正确，你应该看到模型先调用 `analyze_image` 工具，再基于返回结果回答。

---

## 与 Codex 集成

Codex 同样通过 MCP 注册服务器。在其配置文件（如 `~/.codex/config.toml`）中：

```toml
[mcp_servers.deepseek-vision]
command = "python"
args = ["-m", "deepseek_vision_mcp"]
env = { VISION_API_KEY = "your-api-key", VISION_MODEL = "glm-4v-flash", VISION_BASE_URL = "https://open.bigmodel.cn/api/paas/v4" }
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
│       ├── server.py           # MCP Server 入口，analyze_image 工具
│       ├── config.py           # 配置加载（.env / 环境变量 / config.json）
│       ├── image_utils.py      # 图片加载、编码、校验、压缩
│       ├── providers/
│       │   ├── __init__.py     # build_provider 分发
│       │   ├── base.py         # 视觉模型抽象基类（扩展点）
│       │   └── openai_compatible.py
│       └── main.py             # 命令行入口
├── skills/
│   └── vision/
│       └── SKILL.md            # vision Skill 定义
├── examples/
│   ├── test_image.jpg          # 测试图片
│   └── sample_chat.md          # 示例对话
├── scripts/
│   ├── install.sh
│   └── test_mcp.sh
├── tests/                      # pytest 测试
└── .github/workflows/test.yml  # CI
```

---

## 开发与测试

```bash
pip install -e ".[dev]"
pytest -v
```

测试覆盖：本地图片 / URL / base64 三种输入、无效 API Key、文件不存在、
图片超限压缩、格式校验、多提供商切换、配置优先级等。测试全部 mock 掉
外部 API，**不需要真实 Key 即可运行**。

---

## 常见问题 (FAQ)

**Q：报错 `缺少 VISION_API_KEY`？**
A：没有配置 API Key。复制 `.env.example` 为 `.env` 并填入 Key，或用
`deepseek-vision-mcp --check` 定位问题。

**Q：调用工具返回 `VISION_API_ERROR`？**
A：视觉模型 API 调用失败。常见原因：Key 无效、`VISION_BASE_URL` 写错、
模型名不存在、余额不足、网络超时。按工具返回的 `result` 中的提示排查。

**Q：返回 `IMAGE_LOAD_FAILED`？**
A：图片加载失败。检查本地路径是否存在、URL 是否可访问（带 `http(s)://`）、
base64 是否完整。工具会返回具体原因。

**Q：返回 `IMAGE_TOO_LARGE`？**
A：图片压缩后仍超过 `VISION_MAX_IMAGE_SIZE_KB`。换更小的图片，或调大限制。

**Q：支持哪些图片格式？**
A：`jpg / jpeg / png / webp`，可用 `VISION_ALLOWED_FORMATS` 调整。
其他格式会先尝试用 Pillow 识别。

**Q：图片会被压缩吗？**
A：超过大小限制时自动压缩（先降质量，再缩分辨率），不影响识别结果。

**Q：能用免费模型吗？**
A：可以。智谱 `glm-4v-flash` 与硅基流动部分模型提供免费额度，
只需申请 Key 即可，本项目代码本身无需付费。

---

## 隐私说明

- 使用本项目时，**图片内容会被发送到你所配置的第三方视觉模型 API**
  （智谱 AI / 硅基流动 / 通义千问 / OpenAI 等），请勿传入敏感或涉密图片。
- API Key 只保存在你的本机（`.env` / `config.json` / 环境变量），
  项目代码**不内置、不收集、不上传**任何 Key。
- 请求内容（图片 + prompt）由对应服务商的隐私政策约束，
  建议查阅各服务商的隐私条款。
- 若对隐私有严格要求，可选择自建 OpenAI 兼容的视觉推理服务（如 vLLM
  部署 Qwen-VL），把 `VISION_BASE_URL` 指向内网地址。

---

## 许可证

[MIT](./LICENSE)
