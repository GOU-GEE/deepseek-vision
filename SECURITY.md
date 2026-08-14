# Security Policy

## Reporting a vulnerability

请不要在公开 Issue 中披露尚未修复的漏洞。请通过 GitHub 仓库的 Security 页面提交
Private vulnerability report；若该入口不可用，请联系仓库维护者并在标题注明
`[SECURITY] deepseek-vision`。

报告建议包含：受影响版本、复现步骤、影响范围、概念验证，以及可行的修复建议。
维护者会尽快确认收到报告，并在评估后同步修复与披露计划。

## Security boundaries

- 图片和 prompt 会发送给用户配置的第三方视觉模型 API。
- URL 图片默认拒绝私网、回环、保留地址与云元数据地址；每次重定向都会重新校验。
- URL 下载采用流式硬上限，避免无界响应占满内存。
- API Key 不写入日志或工具结果；状态工具只返回 Key 数量和固定掩码。
- 会话缓存只保存图片内容哈希和识别结果，位于进程内存中，退出即清空。
- 剪贴板临时图片在分析后立即删除。

## Release checklist

- 运行 `ruff check .` 与 `pytest -q`。
- 运行 `python -m build` 和 `python -m twine check dist/*`。
- 检查 wheel/sdist 文件列表，确认不包含 `.env`、`config.json`、截图、日志或缓存。
- 分别使用 MCP 1.2.x、1.29.x 与 2.x 完成兼容测试和 stdio 握手冒烟。
- 使用一个权限受限的测试 Key 完成真实单图调用，确认默认模型仍可用。
