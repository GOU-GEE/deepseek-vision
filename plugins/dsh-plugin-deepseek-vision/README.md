# dsh-plugin-deepseek-vision

DeepSeek Harness 视觉插件：为 DeepSeek 等纯文本模型补上「眼睛」。

背后是 [deepseek-vision-mcp](https://github.com/GOU-GEE/deepseek-vision)——
一个 Python MCP Server，把图片交给 OpenAI 兼容视觉模型（默认智谱免费
`glm-4.6v-flash`）识别。本插件用官方 `@deepseek-ai/dsh-mcp-client` 把它
接入 DSH 组合层，工具以 `mcp__deepseek-vision__analyze_image` 等形式暴露，
并随包附带 `vision` Skill（模型遇到图片时自动触发）。

## 前置条件

- DeepSeek Harness（2025-08-13 版本，web profile）
- Python 3.10+，且已安装并配置好 deepseek-vision-mcp：
  ```bash
  pip install -e "path/to/deepseek-vision"
  cp path/to/deepseek-vision/.env.example ~/deepseek-vision/.env   # 填入 VISION_API_KEY
  ```

## 安装

```bash
dsh plugin --profile web add dsh-plugin-deepseek-vision
```

> 若未发布到 npm，可本地安装：`dsh plugin --profile web add file:./plugins/dsh-plugin-deepseek-vision`

安装后**修改 `cordis.patch.yml` 中的 `command`** 为 deepseek-vision 虚拟环境
Python 的绝对路径（如 `/Users/you/deepseek-vision/.venv/bin/python`），
并确保环境里有 `VISION_API_KEY`（或去掉 `env.VISION_API_KEY` 那行，改用
项目 `.env`）。

重启 DSH 后，模型即可调用 `mcp__deepseek-vision__*` 工具。

## 加载 Skill（自动触发）

把包内 `skills/` 复制到 DSH 用户 skill 根目录（默认 `~/.dsh/skills/`）：

```bash
mkdir -p ~/.dsh/skills
cp -r skills/vision ~/.dsh/skills/
```

之后用户发送图片/路径/URL/剪贴板图片或要求「看图/OCR/对比图片」时，
模型会自动调用视觉工具。DSH 会自动热加载（filesystem provider 监视目录）。

## 手动接入（不装插件，等效）

在 profile 的 `cordis.patch.yml` 中直接加：

```yaml
- insert:
    - id: deepseek-vision
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: deepseek-vision
        transport: stdio
        command: /abs/path/to/.venv/bin/python
        args: ['-m', 'deepseek_vision_mcp']
        env:
          VISION_API_KEY: !!js process.env.VISION_API_KEY
          VISION_MODEL: glm-4.6v-flash
          VISION_BASE_URL: https://open.bigmodel.cn/api/paas/v4
```

## 发布说明（给维护者）

- 本包采用 **bundle patch 形态**（`dsh.bundle.patch` → `cordis.patch.yml`），
  插入的 `@deepseek-ai/dsh-mcp-client` / `@deepseek-ai/dsh-skill-filesystem`
  均为 DSH 内置组件，属于已验证路径。
- 社区文档另有一种 **`dsh.mcpServers` 声明形态**（package.json 里直接声明
  server-id → 启动配置，见 make-dsh-plugin skill）；发布前请用
  `dsh --dump-config` 对照当前官方 spec 验证字段契约后再切换。
- 发布到 npm：`npm publish`（`publishConfig.access: public`）。
- 给仓库打标签便于搜索：`gh repo edit GOU-GEE/deepseek-vision --add-topic dsh --add-topic vision --add-topic mcp`

## License

MIT
