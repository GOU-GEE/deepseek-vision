# 发布流程与踩坑记录（v0.3.x 实战总结）

> 发布是不可逆操作。每一步都确认后再执行下一步。
> **所有 Key 必须全程不经过对话、不写入仓库。** 本清单不含任何密钥。

## 发布总流程（已实战验证，直接照做）

### 0. 发布前检查（每次发布必做）

- [ ] `git log --oneline` 确认功能与修复已全部合并到 `main`
- [ ] 版本号统一：`pyproject.toml`、`src/deepseek_vision_mcp/__init__.py`、
      `plugins/dsh-plugin-deepseek-vision/package.json` 与 `package-lock.json`
      四处一致（`grep -rn "<旧版本>" src/ pyproject.toml plugins/.../package*.json` 应为空）
- [ ] ⚠️ **全局排查硬编码版本号**：`scripts/verify_dsh_plugin.py`（已改为动态读
      `__version__`，不要改回去）、`.github/workflows/test.yml`（tarball 名已改为
      动态取版本，不要改回去）。任何 `0.3.x` 硬编码在升版后都会挂 CI。
- [ ] **更新文档**（随本次发布一起提交，别漏）：
      `CHANGELOG.md`（新增本次版本条目）+ `docs/PROJECT_LOG.md`（第 2 节版本号、
      第 6-7 节已完成/待办）。交接日志不过期，才能给新对话/新 Agent 准确信息。
- [ ] 本地验证：`pytest -q` 全绿 + `npm test --prefix plugins/dsh-plugin-deepseek-vision`
      全绿 + `python scripts/verify_dsh_plugin.py` 输出 `[PASS]`
- [ ] 推送到 `main`，等 test workflow 全绿（含 `dsh-plugin` job）

### 1. npm 手动发布（本项目的固定做法）

> 为什么手动：CI 的 OIDC provenance 发布对「已被手动认领的包」会 404
> （OIDC 临时身份 ≠ 包所有者 `lijungou`）。因此 npm 一律**手动发布**，
> CI 的 npm job 已改为**幂等**（版本存在则跳过），不会失败。

```bash
# 新终端，整段执行（PATH 里的 node 是工作区自带的 Node 22）
export PATH="/Users/goulijun/Documents/project/DeepSeek-vision-mcp/.tools/node/bin:$PATH"
export npm_config_cache="/Users/goulijun/Documents/project/DeepSeek-vision-mcp/.tools/npm-cache"
cd /Users/goulijun/Documents/project/DeepSeek-vision-mcp/plugins/dsh-plugin-deepseek-vision
node -p "require('./package.json').version"   # 确认是新版本号
VISION_BUILD_PYTHON=/tmp/py312/python/bin/python3 npm publish --access public
```

- 会打印 `Authenticate your account at: https://www.npmjs.com/auth/cli/...`，
  回车打开浏览器完成 2FA 认证
- 成功标志：`+ dsh-plugin-deepseek-vision@<版本>`
- ⚠️ 本地手动发布**不要加 `--provenance`**（本地无 OIDC 环境会报错）

### 2. 创建 GitHub Release（触发 PyPI 发布）

1. <https://github.com/GOU-GEE/deepseek-vision/releases/new>
2. Tag：`v<版本>`（Target `main`）；标题：`v<版本>`
3. 正文：从 `CHANGELOG.md` 复制对应条目，**检查无旧版本号残留**
4. draft 检查 → Publish
5. `publish.yml` 自动跑：
   - **PyPI**：Trusted Publishing 发布 `deepseek-vision-mcp==<版本>`（项目已存在，直接发）
   - **npm**：幂等检查——版本已存在则跳过（正常情况会跳过）

### 3. 发布后验收（全绿 + 可安装才算完成）

- [ ] GitHub Actions publish run 全绿（badge：`publish - passing`）
- [ ] `pip install deepseek-vision-mcp==<版本>` 在全新 venv 可安装
- [ ] `npm view dsh-plugin-deepseek-vision version` 显示新版本
- [ ] 全新 DSH_HOME 下官方命令可装：
      `npx -y @deepseek-ai/dsh@0.1.0-rc.6 plugin --profile web add dsh-plugin-deepseek-vision`
      （注意：`dsh plugin add` 依赖 **pnpm**，先 `corepack enable && corepack prepare pnpm@11.7.0 --activate`）
- [ ] 配置树确认：`dsh --profile web --dump-config` 含
      `deepseek-vision-host` / `deepseek-vision-mcp` / `launcher.js` / `ELECTRON_RUN_AS_NODE: '1'`

## 已踩过的坑（不要重蹈）

| # | 坑 | 症状 | 修复 |
| --- | --- | --- | --- |
| 1 | 升版后 `verify_dsh_plugin.py` 硬编码 `0.3.0` | CI dsh-plugin job 失败 | 改为动态读 `deepseek_vision_mcp.__version__` |
| 2 | 升版后 `test.yml` 硬编码 tarball 名 `0.3.0.tgz` | CI dsh-plugin job 失败 | 改为 `node -p "require('./package.json').version"` 动态拼接 |
| 3 | CI `npm publish --provenance` 报 404 | OIDC 临时身份不是包所有者 | 手动发布 npm + CI 幂等跳过 |
| 4 | 先手动认领 npm 0.3.0，后发 Release 同版本 | CI 撞版本 | 手动认领与 CI 发布错开版本号 |
| 5 | npm 网页 Granular Token 表单无包选择器 | 个人账号 UI bug | 绕开：手动发布方案，不需要 token |
| 6 | `~/.npm` 缓存 root 属主 | npm 命令 EPERM | 用工作区缓存 `npm_config_cache=.../npm-cache` |
| 7 | GUI shell 无 node/npm | 命令 not found | 用工作区 Node：`.tools/node/bin` + PATH |
| 8 | 本机无 Python 3.10+ | 无法跑测试 | 独立 Python 3.12：`/tmp/py312/python/bin/python3` |

## 回滚须知

- npm 版本不可删除，只可 `npm unpublish`（72 小时内、且无依赖者）或发新版本覆盖
- PyPI 版本不可删除，只能发布新版本
- 因此发布前务必确认版本号、Trusted Publishing 配置与发布内容无误

## 历史版本状态

- `0.3.0`：npm 手动认领（作者发布）；PyPI 无
- `0.3.1`：PyPI 发布成功；npm CI 发布失败（坑 #3），npm 无此版本
- `0.3.2`：npm 手动发布 + PyPI Trusted Publishing，双端一致 ✅ 当前 latest
