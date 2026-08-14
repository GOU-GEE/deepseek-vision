# 示例对话：DeepSeek 通过 deepseek-vision-mcp「看图」

以下对话展示了集成后，用户发送图片时 DeepSeek 主模型如何自动调用
`analyze_image` 工具并基于识别结果回答。

---

## 场景一：本地截图找错误

**用户**：
```
帮我看看 ./screenshot.png 里有什么错误？
```

**DeepSeek（内部流程）**：命中 `skills/vision/SKILL.md` 触发条件
（本地图片路径 + 要求识别错误）→ 调用工具：

```
analyze_image(
  image="./screenshot.png",
  prompt="请识别图片中的错误信息，并说明可能的原因。"
)
```

**工具返回**：
```json
{
  "success": true,
  "result": "截图显示 Python 报错：ModuleNotFoundError: No module named 'requests'，发生在 import requests 处。可能原因：未安装 requests 库。",
  "model": "glm-4.6v-flash",
  "usage": {"prompt_tokens": 1024, "completion_tokens": 180, "total_tokens": 1204}
}
```

**DeepSeek 回答**：
> 这张截图里的错误是 `ModuleNotFoundError: No module named 'requests'`，
> 发生在 `import requests` 这行。解决方法是先执行 `pip install requests`
> 再重新运行程序。如果用了虚拟环境，请确认激活的是同一个环境。

---

## 场景二：URL 图片描述场景

**用户**：
```
这张照片 https://example.com/beach.jpg 是在哪里拍的？
```

**DeepSeek（内部流程）**：输入包含图片 URL → 调用工具：

```
analyze_image(
  image="https://example.com/beach.jpg",
  prompt="请描述图片中的场景、人物、物体和环境细节。"
)
```

**工具返回**：
```json
{
  "success": true,
  "result": "图片拍摄于海边沙滩，背景是蓝色海面和金黄色日落，前景有两个人在散步……",
  "model": "Qwen/Qwen2.5-VL-7B-Instruct",
  "usage": {"prompt_tokens": 900, "completion_tokens": 120, "total_tokens": 1020}
}
```

**DeepSeek 回答**：
> 从画面看，这是海边沙滩的日落场景。沙滩上有两个人在散步，海面在夕阳下
> 呈现金黄色。具体地点无法仅凭画面确定，但很可能是热带或亚热带沿海地区。

---

## 场景三：base64 图片提取文字

**用户**：
```
我有一段截图数据（base64），帮我提取里面的文字：
iVBORw0KGgoAAAANSUhEUgAA...（省略）
```

**DeepSeek（内部流程）**：输入包含 base64 图片数据 → 调用工具：

```
analyze_image(
  image="iVBORw0KGgoAAAANSUhEUgAA...",
  prompt="请提取图片中的所有文字，保持原有排版顺序。"
)
```

**工具返回**：
```json
{
  "success": true,
  "result": "Welcome to DeepSeek Vision\n请登录后继续使用",
  "model": "qwen-vl-plus",
  "usage": {"prompt_tokens": 800, "completion_tokens": 40, "total_tokens": 840}
}
```

**DeepSeek 回答**：
> 图片中的文字是：「Welcome to DeepSeek Vision」和「请登录后继续使用」。

---

## 场景四：失败处理（图片不存在）

**用户**：
```
看看 ./nope.png 里有什么？
```

**工具返回**：
```json
{
  "success": false,
  "error": "IMAGE_LOAD_FAILED",
  "result": "图片文件不存在：./nope.png",
  "model": null,
  "usage": {}
}
```

**DeepSeek 回答**：
> 抱歉，我无法读取 `./nope.png` —— 这个文件不存在。请确认路径是否正确，
> 或改用图片 URL 再试一次。
