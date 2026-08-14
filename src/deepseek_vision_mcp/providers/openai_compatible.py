"""OpenAI 兼容接口的视觉模型实现。

适用于所有提供 ``/chat/completions`` 接口、支持 ``image_url`` 内容块
的服务商，例如：

- 智谱 AI（GLM-4.6V）：``https://open.bigmodel.cn/api/paas/v4``
- 硅基流动（Qwen2.5-VL）：``https://api.siliconflow.cn/v1``
- 通义千问 DashScope：``https://dashscope.aliyuncs.com/compatible-mode/v1``

只需修改 ``VISION_BASE_URL`` / ``VISION_MODEL`` / ``VISION_API_KEY``
即可切换服务商，无需改代码。
"""

from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from .base import BaseVisionProvider, VisionProviderError


class OpenAICompatibleProvider(BaseVisionProvider):
    """基于 ``openai`` 客户端的 OpenAI 兼容视觉模型实现。"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        # 某些网关要求 Authorization 为 "Bearer <key>"，openai 客户端默认即如此。
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)

    def analyze(self, image_data_uri: str, prompt: str) -> Dict[str, Any]:
        """调用视觉模型，返回识别文本与元信息。

        返回 dict 结构：
        {
            "text": "模型返回的识别文本",
            "model": "实际使用的模型名",
            "usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...},
        }
        """
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_data_uri},
                            },
                        ],
                    }
                ],
                max_tokens=2048,
            )
        except Exception as exc:  # 网络错误、401、限流等统一包装
            raise VisionProviderError(
                f"调用视觉模型失败（model={self.model}, base_url={self.base_url}）：{exc}"
            ) from exc

        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise VisionProviderError("视觉模型返回了空内容。")

        usage: Dict[str, Any] = {}
        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return {
            "text": text,
            "model": response.model or self.model,
            "usage": usage,
        }

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
