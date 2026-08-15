# 发布清单（v0.3.1 首次正式发布）

> 发布是不可逆操作。每一步都确认后再执行下一步。
> **所有 Key 必须全程不经过对话、不写入仓库。** 本清单不含任何密钥。

## 0. 前置（已完成）

- [x] 代码冻结：HEAD = `bbec1ca`（含 v0.3.1 版本号），主仓库与验收克隆一致
- [x] 真实 DSH profile 已增量安装 `0.3.0`（与 399775e 哈希一致）
- [x] 人工 UI 验收通过（下拉箭头 / 拖拽遮罩 / 自动插入 / 无重复附件）
- [x] 94 pytest + 18 Node 测试通过；CI Run #19 全绿
- [x] npm / PyPI 均未发布（包名可认领）

## 1. Trusted Publishing 配置（需你在网页端完成，我无法代劳）

### PyPI（项目 `deepseek-vision-mcp`）

1. 登录 <https://pypi.org> → 注册/认领项目 `deepseek-vision-mcp`
   （首次发布需在 "Create a new project" 输入项目名认领）
2. 进入该项目 → **Publishing** → **Add a new pending publisher**：
   - 发行商（Owner）：`GOU-GEE`
   - 仓库（Repository）：`deepseek-vision`
   - 工作流（Workflow）：`publish.yml`
3. 保存后状态为 **pending**，第一次发布成功即变为 **active**

### npm（包 `dsh-plugin-deepseek-vision`）

1. 确认你的 npm 账号（如无：<https://www.npmjs.com/signup>）
2. **首次认领包名**（关键）：由于包名未被占用，需先发布一次。
   方式 A（推荐）：本地 `npm publish --access public` 认领后，
   后续版本走 CI 的 OIDC provenance；
   方式 B：若想纯 CI 发布，需 npm 账号已配置
   GitHub OIDC（npm 的 trusted publishing 走 `--provenance`，
   要求账号与 GitHub 身份关联）。
3. 确认 `publish.yml` 中 `registry-url: https://registry.npmjs.org` 与
   `npm publish --access public --provenance` 与你的账号配置匹配。

### GitHub

- 无需额外配置；Release 由你在网页端创建（见第 2 步）。

## 2. 创建 GitHub Release v0.3.1（触发发布）

1. 打开 <https://github.com/GOU-GEE/deepseek-vision/releases/new>
2. 标签（Tag）：`v0.3.1`（不要用 v0.3.0——npm 0.3.0 已手动认领，CI 会撞版本）（目标：`main`）
3. 标题：`v0.3.1`
4. 正文：粘贴 [CHANGELOG.md](../CHANGELOG.md) 的 v0.3.1 条目
5. **先点 "Save draft" 检查无误，再点 "Publish release"**
6. 发布后 `publish.yml` 自动运行：
   - PyPI：构建 wheel/sdist → Twine check → Trusted Publishing 上传
   - npm：构建 Bundle（含 Python wheel）→ `npm test` → `npm publish --provenance`
7. 等待两个 job 全绿

## 3. 发布后验收（全绿 + 可安装才算完成）

- [ ] GitHub Actions Run（publish）全绿
- [ ] `pip install deepseek-vision-mcp==0.3.1` 可安装
- [ ] `npm view dsh-plugin-deepseek-vision` 显示 0.3.1
- [ ] 全新环境 `dsh plugin --profile web add dsh-plugin-deepseek-vision`
      可安装（不再用 tarball）
- [ ] README 公开安装命令可执行（`pip install` / `dsh plugin add`）

## 4. 宣发（前三步全部完成后再做）

- GitHub Discussions / Release 通知
- 若有意向：README 顶部补 npm/PyPI 安装徽章

## 回滚须知

- npm 版本不可删除，只可 `npm unpublish`（72 小时内、且无依赖者）或发
  新版本覆盖
- PyPI 版本不可删除，只能发布新版本
- 因此发布前务必确认 1、2 两步配置正确、发布内容无误
