"""预置任务提示词。

借鉴 deepseek-eyes（Shaohan-He/deepseek-eyes）的设计：把高频任务
（OCR、UI 描述、报错诊断、图表解读等）的提示词预置好，主模型只需
传入 ``task`` 名即可获得高质量、稳定的视觉指令，无需自行拼 prompt。

``analyze_image`` 工具的 ``task`` 参数即从此处取值。
"""

from __future__ import annotations

from typing import Dict, Literal

# 任务名（同时是 MCP 工具 task 参数的枚举值）
TaskName = Literal[
    "describe",
    "ocr",
    "describe_ui",
    "diagnose_error",
    "understand_diagram",
    "analyze_chart",
    "code_from_screenshot",
]

DEFAULT_PROMPT = "请详细描述这张图片的内容"

TASK_PROMPTS: Dict[str, str] = {
    "describe": DEFAULT_PROMPT,
    "ocr": (
        "提取这张图片中的全部文字。只返回文字内容，保留排版和换行，不做任何评论。"
    ),
    "describe_ui": (
        "分析这张 UI 截图。描述：1) 整体布局 2) 组件（按钮、表单、导航、输入框）"
        " 3) 可见文字和标签 4) 状态（错误提示、激活标签页、弹窗等）。"
    ),
    "diagnose_error": (
        "分析这张错误截图。返回：1) 精确的错误信息 2) 可能的原因 "
        "3) 具体的修复步骤 4) 如何避免再次发生。"
    ),
    "understand_diagram": (
        "解读这张图表。返回：1) 图表类型 2) 组成部分及其作用 "
        "3) 关系/流程 4) 整体目的。"
    ),
    "analyze_chart": (
        "分析这张数据图表。返回：1) 图表类型 2) 坐标轴和标签 "
        "3) 关键趋势 4) 值得注意的数据点 5) 洞察。"
    ),
    "code_from_screenshot": (
        "从这张截图中提取全部代码。返回：1) 编程语言 2) 格式化的代码块，保留缩进。"
    ),
}

# 供工具 docstring 使用的任务说明（帮助主模型选择 task）
TASK_DESCRIPTIONS: Dict[str, str] = {
    "describe": "通用：详细描述图片内容",
    "ocr": "提取图片中的全部文字",
    "describe_ui": "描述 UI 截图的布局、组件与状态",
    "diagnose_error": "诊断错误截图的原因并给出修复步骤",
    "understand_diagram": "解读流程图/架构图等图表",
    "analyze_chart": "分析数据图表中的趋势与洞察",
    "code_from_screenshot": "从代码截图提取可编辑代码",
}
