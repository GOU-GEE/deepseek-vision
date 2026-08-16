"""deepseek_vision_mcp — 让 DeepSeek 等纯文本模型获得图片理解能力。

通过 MCP Server 暴露 ``analyze_image`` 工具，将图片交给第三方
OpenAI 兼容视觉模型 API 识别，并把识别结果返回给主模型。
"""

from .config import VisionConfig, load_config

__version__ = "0.4.0"

__all__ = ["load_config", "VisionConfig", "__version__"]
