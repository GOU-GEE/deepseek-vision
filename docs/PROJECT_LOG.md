# PROJECT LOG — deepseek-vision-mcp 项目交接日志

> **给新对话 / 新 Agent 的第一份资料。** 先读本文件，再看
> [README.md](README.md)（对外文档）、[docs/RELEASING.md](docs/RELEASING.md)
> （发布流程）、[docs/BENCHMARK.md](docs/BENCHMARK.md)（对比测试）、
> [CHANGELOG.md](CHANGELOG.md)（版本历史）。
>
> 最后更新：2026-08-16

---

## 1. 项目是什么

给 **DeepSeek（纯文本模型）补视觉能力**：MCP Server + DeepSeek Harness（DSH）原生插件。

- **原理**：DeepSeek 不直接「看」图；用户发图片时，主模型调用视觉工具，把图片交给
  OpenAI 兼容视觉模型（默认智谱免费 `glm-4.6v-flash`）识别，识别文本再喂回 DeepSeek。
- **GitHub**：https://github.com/GOU-GEE/deepseek-vision
- **当前版本**：`0.3.2`（PyPI 与 npm 双端一致）
- **许可证**：MIT

## 2. 交付物（均已发布）

| 形态 | 包名 / 地址 | 版本 |
| --- | --- | --- |
| Python MCP Server | PyPI `deepseek-vision-mcp` | 0.3.2 |
| DSH 原生插件（bundle） | npm `dsh-plugin-deepseek-vision` | 0.3.2 |
| 源码 | GitHub `GOU-GEE/deepseek-vision`，分支 `main` | 最新提交见 `git log` |

**4 个 MCP 工具**：`analyze_image`（单图，路径/URL/base64）、`analyze_clipboard`
（剪贴板读图，Win/macOS/Linux）、`compare_images`（2-4 张多图对比）、
`vision_status`（健康检查）。另有一个 `task` 参数提供 7 种预置任务
（describe/ocr/describe_ui/diagnose_error/understand_diagram/analyze_chart/
code_from_screenshot）。

## 3. 用户怎么用

```bash
# Python（任意 MCP 客户端）
pip install deepseek-vision-mcp
cp .env.example .env   # 填 VISION_API_KEY（智谱免费 Key：open.bigmodel.cn）
deepseek-vision-mcp

# DeepSeek Harness 一键插件（装一次 = 主体 + MCP 桥两个实例，用户无感知）
dsh plugin --profile web add dsh-plugin-deepseek-vision
cp -r skills/vision ~/.dsh/skills/
```

- **一个包 → 两个实例**（`deepseek-vision-host` 主体 + `deepseek-vision-mcp` 工具桥），
  这是 bundle 设计，不是重复安装，用户不需要分别装。
- 配置页：设置 → 插件 → DeepSeek Vision（多服务商、主/备用 Key、测试按钮）。
- Key 存 DSH 官方凭据存储，不落库、不入日志、不进模型上下文。

## 4. 支持的服务商（OpenAI 兼容，改三个环境变量即可切换）

| 服务商 | VISION_BASE_URL | VISION_MODEL |
| --- | --- | --- |
| 智谱 AI（默认） | https://open.bigmodel.cn/api/paas/v4 | `glm-4.6v-flash`（免费） |
| 硅基流动 | https://api.siliconflow.cn/v1 | `Qwen/Qwen2.5-VL-7B-Instruct` |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | `qwen-vl-plus` |

关键环境变量：`VISION_API_KEY`（必填）、`VISION_API_KEYS`（多 Key 逗号分隔，429 轮换）、
`VISION_MODELS`（同服务商降级链）、`VISION_FALLBACK_API_KEY`（备用服务商）、
`VISION_MAX_ATTEMPTS`（默认 4）、`VISION_CACHE_ENABLED`（LRU+TTL 缓存）、
`VISION_TEMPERATURE`（默认 0.3）、`VISION_ALLOW_PRIVATE_IMAGE_URLS`（SSRF 开关，默认 false）。

## 5. 核心架构与文件

```
src/deepseek_vision_mcp/
├── server.py            # 4 个 MCP 工具 + JSON 信封 + 缺失 Key 引导
├── config.py            # 配置：环境变量 > .env > config.json > 默认值
├── image_utils.py       # 三态输入加载、魔数校验、压缩、SSRF 防护
├── clipboard.py         # 跨平台剪贴板（PIL/pngpaste/wl-paste/xclip）
├── prompts.py           # 7 种预置任务提示词
├── cache.py             # 识别结果缓存（LRU+TTL）
├── providers/           # base 抽象 + openai_compatible（多Key轮换/模型降级/token升档）
├── main.py              # CLI：--check / --check-clipboard / --test-image
└── __main__.py
plugins/dsh-plugin-deepseek-vision/   # DSH bundle（client.js 粘贴/拖拽桥 + launcher.js + 内置 wheel）
skills/vision/SKILL.md                # 自动触发 Skill
scripts/benchmark.py                  # 可复现对比测试（见 docs/BENCHMARK.md）
scripts/verify_dsh_plugin.py          # DSH 托管运行时握手验收
.github/workflows/test.yml            # 测试 + dsh-plugin + lint + mcp 兼容矩阵
.github/workflows/publish.yml         # Release 触发 → PyPI/npm 发布
```

## 6. 已完成的近期工作（2026-08-14 ~ 08-16）

- ✅ 首次正式发布：PyPI + npm 双端 `0.3.2`（发布流程与踩坑见 docs/RELEASING.md）
- ✅ DSH 桌面版插件：可视化配置页、粘贴/拖拽图片自动触发、自动 Python 运行时引导
- ✅ awesome-dsh-plugin 收录：**PR #583 已合并**（列表 Tools & Capabilities 分类）
- ✅ **市场截图收录：PR #987 已合并**（5 张截图已进 `data/screenshots.json`，
  dsh-market ≥1.8.0 以 AppStore 风格展示；截图已打码本地路径，隐私安全）
- ✅ 仓库 Topics：`dsh-plugin` 等 11 个
- ✅ README：收录徽章 + 「与 DSH 原生视觉/其他插件区别」章节
- ✅ 可复现对比测试 benchmark（5 子命令）

## 7. 待办 / 进行中

1. **首轮宣发**（下一步可选）：GitHub Discussions / 社交媒体简介；市场截图已就绪，
   可在 dsh-market ≥1.8.0 验证 AppStore 风格展示效果。
2. 真实 DSH profile 已在 0.3.2（npm 版）+ dsh-market 1.3.1（更新提示为发布安全期，
   可点「立即更新」或等满一天）；用户 Key 未触碰。
3. 未来优化候选（按价值排序，未实施）：
   - `retry_last_image` 零参数重试工具（失败图内存暂存）
   - TOOLS 工具白名单（省主模型上下文）
   - `thinking` 参数透传
   - CI 加 ruff 已做；可再加 publish 徽章等

## 8. 本机环境要点（开发这台机器专用）

- **Python**：系统只有 3.9；测试/构建用独立 Python 3.12：
  `/tmp/py312/python/bin/python3`（内含已装依赖；若被清，用 python-build-standalone
  重新下载解压后 `pip install -e ".[dev]"`）。
- **Node/npm**：系统无 node；用工作区自带 Node 22：
  `export PATH="/Users/goulijun/Documents/project/DeepSeek-vision-mcp/.tools/node/bin:$PATH"`
- **npm 缓存**：`~/.npm` 有 root 属主文件，发布时用工作区缓存：
  `export npm_config_cache=".../.tools/npm-cache"`
- **git 推送**：本机代理封锁 SSH 22，走 443；主机密钥在工作区 `.git/known_hosts_443`：
  ```bash
  GIT_SSH_COMMAND="ssh -o UserKnownHostsFile=$PWD/.git/known_hosts_443" git push origin main
  ```
- **网络代理不稳定**：曾出现全站断连（curl 返回 000）。ssh.github.com:443 优先。
- **npm 发布约定**：手动发布（`npm publish --access public`，浏览器 2FA 认证），
  CI 发布已幂等（版本存在则跳过）——详见 docs/RELEASING.md。
- **PyPI**：Trusted Publishing 已配置（GOU-GEE/deepseek-vision → publish.yml），
  Release 触发自动发布。

## 9. 测试与验收（改动后必跑）

```bash
cd /Users/goulijun/Documents/project/DeepSeek-vision-mcp
/tmp/py312/python/bin/python3 -m pytest -q                    # Python 测试（94 个）
export PATH=".../.tools/node/bin:$PATH"                       # Node 测试需要
npm test --prefix plugins/dsh-plugin-deepseek-vision           # 插件 Node 测试（18 个）
/tmp/py312/python/bin/python3 -m ruff check .                  # lint
VISION_BUILD_PYTHON=/tmp/py312/python/bin/python3 \
  /tmp/py312/python/bin/python3 scripts/verify_dsh_plugin.py   # MCP 握手验收
```

## 10. 易踩的坑（重要）

- **升版必须全局同步**：`pyproject.toml`、`src/.../__init__.py`、
  `plugins/.../package.json`、`package-lock.json` 四处一致；并全局 grep 旧版本号
  （`verify_dsh_plugin.py` 与 `test.yml` 曾硬编码版本导致 CI 挂，现已动态化，别改回去）。
- **不要直接改 `~/.dsh` 之外的内容**：用户 Key 在 DSH 凭据存储，任何操作不得读取/输出/覆盖。
- **改动工具行为要同步 SKILL.md**（主模型靠它触发）。
- README / CHANGELOG / docs 与代码同步更新，保持交接文档不失效。
