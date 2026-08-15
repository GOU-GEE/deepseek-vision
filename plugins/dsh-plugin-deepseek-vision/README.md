# dsh-plugin-deepseek-vision

DeepSeek Harness 原生视觉 Bundle。文本版 DeepSeek 遇到图片时，通过随包托管的
`deepseek-vision-mcp` 调用 OpenAI 兼容视觉模型；默认使用智谱免费的
`glm-4.6v-flash`。

## 能力

- DSH Web 中直接粘贴或拖入 PNG/JPEG/GIF/WebP；插件保存为权限 `0600` 的临时文件，
  并把明确的视觉工具调用指令插入输入框。
- 自动安装版本锁定的 Python MCP 后端到 `$DSH_HOME/cache`，无需克隆仓库、创建
  虚拟环境或修改 Python 绝对路径。
- 保留 `analyze_image`、`analyze_clipboard`、`compare_images`、`vision_status`
  四个工具，以及多 Key 轮换、模型降级、缓存和 SSRF 防护。
- 可视化配置主、备用服务商；429/5xx 自动退避、跨服务商切换并短期熔断，单次工具
  调用默认最多发出 4 次真实视觉请求。
- 桌面版直接使用 App 内置 Node；缺少 Python 3.10+ 时自动下载校验后的 uv，并在
  `$DSH_HOME/cache` 准备隔离 CPython 3.12。
- 只接管明确选中的文本版 DeepSeek；原生视觉模型继续走 DSH 默认图片链路。

## 要求

- DeepSeek Harness `0.1.0-rc.5` / `0.1.0-rc.6`（兼容目标：`>=0.1.0-rc.5 <0.2.0`）
- 使用 DSH 桌面版时无需另装 Node；从源码构建才需要 Node.js `22.19+` 或 `24+`
- 从源码安装才需要 Corepack/pnpm；安装已发布的 Bundle 由 DSH 安装器处理
- 有 Python `3.10+` 时直接复用；没有时插件自动准备隔离 CPython 3.12
- 首次启动需要访问 GitHub Releases 与 PyPI；后续启动复用本地缓存

## 安装

正式发布后，把智谱 Key 放入启动 DSH 的环境，然后安装 Bundle：

```bash
export VISION_API_KEY='你的智谱APIKey'
npx -y @deepseek-ai/dsh@0.1.0-rc.6 plugin --profile web add dsh-plugin-deepseek-vision@0.3.0
npx -y @deepseek-ai/dsh@0.1.0-rc.6 web
```

Windows PowerShell：

```powershell
$env:VISION_API_KEY = '你的智谱APIKey'
npx -y @deepseek-ai/dsh@0.1.0-rc.6 plugin --profile web add dsh-plugin-deepseek-vision@0.3.0
npx -y @deepseek-ai/dsh@0.1.0-rc.6 web
```

> `0.3.0` 发布到 npm 前，请在本仓库运行
> `VISION_BUILD_PYTHON=python3 npm pack`，再把生成的 `.tgz` 安装进 profile。
> Bundle 自带同版本 Python wheel，避免前后端版本漂移。

正式 npm Bundle 的普通安装目标是 1-3 分钟；仅当系统没有 Python 3.10+ 时，首次
准备隔离 CPython 可能额外需要 2-8 分钟。源码构建、全套测试和真实 API 验收属于
发布审计流程，通常需要 15-30 分钟，不是最终用户的日常安装路径。

## 配置

macOS 桌面版安装并重启后，进入：

```text
设置 → 插件 → 插件配置 → DeepSeek Vision
```

选择智谱、硅基流动、通义千问或自定义 OpenAI 兼容服务，页面会联动推荐模型与
Base URL。可启用第二家备用服务，并单独填写、测试备用 Key。保存后用 `Cmd+Q` 完全
退出并重新打开 DSH，让 MCP 进程读取新配置。两个 Key 分别存入 DSH 官方凭据存储，
页面只显示配置状态且不会回显原文。测试连接会发送一张 1×1 图片并请求最多 8 tokens。

运行时默认采用 4 次全局请求预算：单个端点至多重试一次，然后尝试备用 Key、模型或
备用服务商；429/5xx 端点默认熔断 90 秒。工具结果中的 `provider`、`fallback_used` 和
`attempts` 会说明实际走了哪条链路。可用 `VISION_MAX_ATTEMPTS`（1-12）与
`VISION_CIRCUIT_COOLDOWN_SECONDS`（5-3600）调整。

默认值：

```env
VISION_MODEL=glm-4.6v-flash
VISION_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

环境变量的优先级高于可视化配置。还可在启动 DSH 前设置 `VISION_API_KEYS`、
`VISION_MODELS` 等变量。也可以把
`VISION_API_KEY: "你的Key"` 写入 DSH 官方凭据文件 `$DSH_HOME/.credentials.yaml`
（文件权限应为 `0600`）；环境变量优先。Key、模型和 Base URL 必须来自同一服务商。
不要把 Key 写进 `cordis.patch.yml`、普通配置文件或 Git 仓库。

## 验证

启动后选择文本版 DeepSeek，把一张截图粘贴或拖入输入框。输入框应出现类似：

```text
请调用 mcp__deepseek-vision__analyze_image 分析我刚粘贴的图片：/tmp/deepseek-vision-dsh-.../paste.png
```

发送后应出现视觉工具调用。也可运行：

```bash
dsh --profile web --dump-config | grep deepseek-vision
```

## 隐私与安全

- 图片会发送给用户配置的第三方视觉模型服务。
- 粘贴接口限制为 20 MB、拒绝跨站浏览器请求，并用魔数而不是扩展名识别图片；
  权限 `0600` 的临时目录会在一小时后自动清理。
- URL 默认拒绝回环、私网、元数据地址和 DNS rebinding。
- API Key 不写入 npm 包、配置 patch、日志或模型上下文。

## 发布

```bash
npm test
VISION_BUILD_PYTHON=python3 npm pack --dry-run
npm publish
```

DSH 是 Developer Preview，发版前必须在官方当前 RC 上重新执行干净 profile
安装和真实图片验收。

MIT
