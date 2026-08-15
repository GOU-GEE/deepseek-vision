---
name: vision
description: >-
  当用户发送图片、图片路径（本地或 URL）、剪贴板图片、base64 图片数据，
  或要求识别、理解、描述、对比图片内容（如提取文字、描述场景、查找错误、
  识别对象、截图分析、对比两张图）时，自动调用视觉工具 analyze_image /
  analyze_clipboard / compare_images，借助第三方视觉模型完成图片理解。
---

# Vision Skill — 图片理解

DeepSeek 主模型是纯文本模型，无法直接“看”图片。本 Skill 通过 MCP 工具
（`analyze_image` / `analyze_clipboard` / `compare_images`）把图片交给第三方
OpenAI 兼容视觉模型（如智谱 GLM-4.6V、硅基流动 Qwen2.5-VL、通义千问
qwen-vl-plus），再把识别文本返回给主模型。

## 触发条件

满足以下任一条件时，**必须**调用视觉工具，而不是假装能看到图片：

1. 用户输入中包含**本地图片路径**，例如 `./screenshot.png`、`~/Desktop/photo.jpg`、
   或绝对路径 `/Users/me/1.png`。
2. 用户输入中包含**图片 URL**，例如 `https://example.com/foo.png`。
3. 用户输入中包含 **base64 图片数据**（可能带 `data:image/...;base64,` 前缀）。
4. 用户提到**剪贴板**：说「看看剪贴板里有什么」「我截图了」「刚复制的图片」
   ——调用 `analyze_clipboard`。
5. 用户要求**对比多张图片**：说「对比这两张图」「这两张有什么区别」——调用
   `compare_images`，把各图片路径/URL 放进 `images` 数组。
6. 用户明确要求**识别 / 理解 / 描述**图片内容，例如：
   - “帮我看看这张图里有什么错误”
   - “提取这张图片里的文字”
   - “这张截图显示了什么报错信息？”
   - “描述一下这张照片的场景”
7. 用户上传了图片但主模型无法直接处理（例如在 DeepSeek Harness /
   Codex 中以附件形式传入），此时同样应调用工具。

## 必须执行的操作

1. **先确认工具可用**：调用前确认当前会话工具列表里有对应的视觉工具。
   若没有，说明 MCP 未加载，提示用户检查配置并重启，**不要硬编造结果**。
2. 判断图片输入形式：本地路径 / URL / base64 / 剪贴板，选择对应工具：
   - 单张图片 → `analyze_image(image=..., prompt=?, task=?)`
   - 剪贴板图片 → `analyze_clipboard(prompt=?, task=?)`
   - 多图对比 → `compare_images(images=[...], prompt=?)`
3. 选择 `task`（预置任务，无需自己拼 prompt；也可用 `prompt` 自定义指令，
   `prompt` 优先级更高）：

   | task | 用途 | 效果 |
   | --- | --- | --- |
   | `describe`（默认） | 通用描述 | 详细描述图片内容 |
   | `ocr` | 提取文字 | 逐字提取，保留排版换行，不做评论 |
   | `describe_ui` | UI 截图 | 布局 / 组件 / 可见文字 / 状态 |
   | `diagnose_error` | 报错截图 | 错误信息 / 原因 / 修复步骤 |
   | `understand_diagram` | 流程图/架构图 | 类型 / 组成 / 关系 / 目的 |
   | `analyze_chart` | 数据图表 | 类型 / 坐标轴 / 趋势 / 洞察 |
   | `code_from_screenshot` | 代码截图 | 语言 / 可编辑代码块 |

   自定义 `prompt` 示例：
   - 提取文字：`请提取图片中的所有文字，保持原有排版顺序。`
   - 找错误：`请识别图片中的错误信息，并说明可能的原因。`
   - 描述场景：`请描述图片中的场景、人物、物体和环境细节。`
   - 其他需求：把用户的原始诉求改写为对视觉模型的清晰指令。

4. 调用 MCP 工具：

   ```
   analyze_image(image="<路径或URL或base64>", task="ocr")
   analyze_clipboard(task="diagnose_error")
   compare_images(images=["./a.png", "https://example.com/b.jpg"], prompt="对比两者差异")
   ```

5. 工具返回 JSON：`{"success": true/false, "result": "...", "model": "...", "provider": "...", "fallback_used": true/false, "attempts": 0, "usage": {...}, "cached": true/false}`。
   - `success: true`：把 `result` 中的识别文本直接作为回答呈现给用户，
     可适当补充说明（来自哪个模型）；`cached: true` 只表示命中同会话缓存，
     内容仍可正常使用。
   - `success: false`：把 `error` 字段（如 `IMAGE_LOAD_FAILED`、
     `VISION_API_ERROR`、`CONFIG_ERROR`、`CLIPBOARD_ERROR`）和 `result` 中的
     错误信息转告用户，并给出修复建议（检查路径/URL 是否有效、API Key 是否
     配置、图片是否超限、剪贴板是否有图等）。

## 注意事项

- **不要编造图片内容**：模型看不到图片时，**禁止**凭空描述图片。
- **限流节奏**：Server 会在全局请求预算内自动退避、轮换 Key/模型并切换已配置的
  备用服务商，`fallback_used: true` 表示已自动降级。只有在工具最终仍返回
  `VISION_API_ERROR` 且提示限流（429）时，才等待 15~30 秒再调用一次；仍失败则
  如实告知，**不要无限空转**。
- `image` 参数必须是字符串；URL 必须带 `http(s)://` 前缀；默认拒绝内网 URL
  （SSRF 防护），如需访问内网图片服务请配置 `VISION_ALLOW_PRIVATE_IMAGE_URLS=true`。
- 本地路径以调用方（MCP Server）所在机器的文件系统为准。
- 图片会发送给第三方视觉模型 API，涉及隐私时应提醒用户。
- 工具超时或网络异常时，工具会返回 `success: false`，如实转告即可。
- 不要把 API Key 写进任何 prompt 或输出。

## 示例对话

### 示例 1：本地截图找错误

**用户**：帮我看看 ./screenshot.png 里有什么错误？

**助手**：我来识别这张截图的内容。

```
调用 analyze_image(image="./screenshot.png", task="diagnose_error")
```

**工具返回**：`{"success": true, "result": "截图显示 Python 报错：ModuleNotFoundError: No module named 'requests'，发生在 import requests 处。可能原因：未安装 requests 库……", "model": "glm-4.6v-flash", ...}`

**助手**：这张截图里的错误是 `ModuleNotFoundError: No module named 'requests'`，
发生在 `import requests` 这行。解决方法是执行 `pip install requests` 后重新运行。

### 示例 2：剪贴板图片（用户刚截图）

**用户**：看看我刚复制的截图里有什么？

**助手**：我来读取剪贴板中的图片。

```
调用 analyze_clipboard()
```

**工具返回**：`{"success": true, "result": "这是一张数据图表，X 轴为月份，Y 轴为销售额，3 月达到峰值……", ...}`

**助手**：你复制的截图是一张月度销售额图表，3 月达到峰值……

### 示例 3：多图对比

**用户**：对比一下 design_v1.png 和 design_v2.png 有什么不同？

**助手**：我来对比这两张图。

```
调用 compare_images(images=["./design_v1.png", "./design_v2.png"])
```

**工具返回**：`{"success": true, "result": "两张图都是登录页设计。主要差异：1) v2 的按钮从蓝色改为绿色……", ...}`

**助手**：两张设计稿的主要差异是……

### 示例 4：图片加载失败

**工具返回**：`{"success": false, "error": "IMAGE_LOAD_FAILED", "result": "图片文件不存在：./nope.png"}`

**助手**：抱歉，我无法读取 `./nope.png` —— 这个文件不存在。请确认路径是否正确，
或改用图片 URL 再试一次。
