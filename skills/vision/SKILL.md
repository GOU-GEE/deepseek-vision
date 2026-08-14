---
name: vision
description: >-
  当用户发送图片、图片路径（本地或 URL），或要求识别、理解、描述图片内容
  （如提取文字、描述场景、查找错误、识别对象）时，自动调用视觉工具
  analyze_image，借助第三方视觉模型完成图片理解。
---

# Vision Skill — 图片理解

DeepSeek 主模型是纯文本模型，无法直接“看”图片。本 Skill 通过 MCP 工具
`analyze_image` 把图片交给第三方 OpenAI 兼容视觉模型（如智谱 GLM-4V、
硅基流动 Qwen2.5-VL、通义千问 qwen-vl-plus），再把识别文本返回给主模型。

## 触发条件

满足以下任一条件时，**必须**调用 `analyze_image` 工具，而不是假装能看到图片：

1. 用户输入中包含**本地图片路径**，例如 `./screenshot.png`、`~/Desktop/photo.jpg`、
   或绝对路径 `/Users/me/1.png`。
2. 用户输入中包含**图片 URL**，例如 `https://example.com/foo.png`。
3. 用户输入中包含 **base64 图片数据**（可能带 `data:image/...;base64,` 前缀）。
4. 用户明确要求**识别 / 理解 / 描述**图片内容，例如：
   - “帮我看看这张图里有什么错误”
   - “提取这张图片里的文字”
   - “这张截图显示了什么报错信息？”
   - “描述一下这张照片的场景”
5. 用户上传了图片但主模型无法直接处理（例如在 DeepSeek Harness /
   Codex 中以附件形式传入），此时同样应调用工具。

## 必须执行的操作

1. 判断图片输入形式：本地路径 / URL / base64。
2. 根据用户问题构造 `prompt`（传给视觉模型的任务描述）：
   - **通用描述**：用户只是让“看看这张图”时，用默认提示词
     `请详细描述这张图片的内容`。
   - **提取文字**：`请提取图片中的所有文字，保持原有排版顺序。`
   - **找错误**（报错截图）：`请识别图片中的错误信息，并说明可能的原因。`
   - **描述场景**：`请描述图片中的场景、人物、物体和环境细节。`
   - **识别界面元素**：`请描述图片中的界面布局和关键元素。`
   - 其他需求：把用户的原始诉求改写为对视觉模型的清晰指令。
3. 调用 MCP 工具：

   ```
   analyze_image(image="<路径或URL或base64>", prompt="<按上面规则构造的提示词>")
   ```

4. 工具返回 JSON：`{"success": true/false, "result": "...", "model": "...", "usage": {...}}`。
   - `success: true`：把 `result` 中的识别文本直接作为回答呈现给用户，
     可适当补充说明（来自哪个模型）。
   - `success: false`：把 `error` 字段（如 `IMAGE_LOAD_FAILED`、
     `VISION_API_ERROR`）和 `result` 中的错误信息转告用户，并给出修复建议
     （检查路径/URL 是否有效、API Key 是否配置、图片是否超限等）。

## 注意事项

- 不要编造图片内容：模型看不到图片时，**禁止**凭空描述图片。
- `image` 参数必须是字符串；URL 必须带 `http(s)://` 前缀。
- 本地路径以调用方（MCP Server）所在机器的文件系统为准。
- 图片会发送给第三方视觉模型 API，涉及隐私时应提醒用户。
- 工具超时或网络异常时，工具会返回 `success: false`，如实转告即可。

## 示例对话

### 示例 1：本地截图找错误

**用户**：帮我看看 ./screenshot.png 里有什么错误？

**助手**：我来识别这张截图的内容。

```
调用 analyze_image(image="./screenshot.png", prompt="请识别图片中的错误信息，并说明可能的原因。")
```

**工具返回**：`{"success": true, "result": "截图显示 Python 报错：ModuleNotFoundError: No module named 'requests'，发生在 import requests 处。可能原因：未安装 requests 库……", "model": "glm-4v-flash", ...}`

**助手**：这张截图里的错误是 `ModuleNotFoundError: No module named 'requests'`，
发生在 `import requests` 这行。解决方法是执行 `pip install requests` 后重新运行。

### 示例 2：URL 图片描述场景

**用户**：这张照片 https://example.com/beach.jpg 是在哪里拍的？

**助手**：我来分析这张图片。

```
调用 analyze_image(image="https://example.com/beach.jpg", prompt="请描述图片中的场景、人物、物体和环境细节。")
```

**工具返回**：`{"success": true, "result": "图片拍摄于海边沙滩，背景是蓝色海面和日落……", ...}`

**助手**：从画面看，这是海边沙滩的日落场景……

### 示例 3：图片加载失败

**工具返回**：`{"success": false, "error": "IMAGE_LOAD_FAILED", "result": "图片文件不存在：./nope.png"}`

**助手**：抱歉，我无法读取 `./nope.png` —— 这个文件不存在。请确认路径是否正确，
或改用图片 URL 再试一次。
