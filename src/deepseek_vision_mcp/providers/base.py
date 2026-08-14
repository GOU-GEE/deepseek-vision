"""视觉模型调用抽象基类。

新接入一个服务商时，继承 :class:`BaseVisionProvider` 并实现
:meth:`analyze`，然后在 ``providers/__init__.py`` 的
:func:`build_provider` 中注册即可。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class VisionProviderError(Exception):
    """调用视觉模型失败。"""


class BaseVisionProvider(ABC):
    """视觉模型提供商的统一接口。"""

    @abstractmethod
    def analyze(self, image_data_uri: str, prompt: str) -> Dict[str, Any]:
        """分析图片并返回识别结果。

        参数:
            image_data_uri: 形如 ``data:image/jpeg;base64,....`` 的图片。
            prompt: 对视觉模型的任务描述。

        返回:
            dict，至少包含 ``text``（识别文本）。实现方可以附加
            ``model``、``usage`` 等元信息，由上层合并进最终输出。
        """
        raise NotImplementedError

    def close(self) -> None:
        """释放底层客户端资源（可选实现）。"""
