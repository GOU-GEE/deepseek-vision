"""视觉模型提供商抽象层。"""

from .base import BaseVisionProvider, VisionProviderError
from .openai_compatible import OpenAICompatibleProvider

__all__ = [
    "BaseVisionProvider",
    "VisionProviderError",
    "OpenAICompatibleProvider",
    "build_provider",
]


def build_provider(config) -> BaseVisionProvider:
    """根据配置的 ``VISION_PROVIDER`` 构建提供商实例。

    当前仅实现 ``openai_compatible``（默认）。未来接入特殊接口格式的
    服务商时，在此处按名称分发即可。
    """
    name = getattr(config, "provider", "openai_compatible")
    if name in ("openai", "openai_compatible"):
        return OpenAICompatibleProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            temperature=getattr(config, "temperature", 0.3),
        )
    raise VisionProviderError(
        f"未知的提供商类型：{name!r}。当前支持：openai_compatible。"
    )
