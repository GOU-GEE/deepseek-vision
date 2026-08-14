"""OpenAI 兼容接口的视觉模型实现。

适用于所有提供 ``/chat/completions`` 接口、支持 ``image_url`` 内容块
的服务商，例如：

- 智谱 AI（GLM-4.6V）：``https://open.bigmodel.cn/api/paas/v4``
- 硅基流动（Qwen2.5-VL）：``https://api.siliconflow.cn/v1``
- 通义千问 DashScope：``https://dashscope.aliyuncs.com/compatible-mode/v1``

只需修改 ``VISION_BASE_URL`` / ``VISION_MODEL`` / ``VISION_API_KEY``
即可切换服务商，无需改代码。

健壮性设计（借鉴 image-vision-mcp / staticdeng）：
- 客户端内置重试（429/5xx/连接错误，指数退避，默认 2 次）
- 输出被 ``max_tokens`` 截断（``finish_reason=="length"``）时自动升档重试
- 空内容诊断：区分「被截断」与「推理模型只返回了 reasoning_content」
- 错误按 HTTP 状态码附中文修复指引，让主模型能直接转述给用户
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import openai
from openai import OpenAI

from .base import BaseVisionProvider, VisionProviderError

logger = logging.getLogger("deepseek_vision_mcp")

# 输出 token 升档步进：被截断时逐档放大重试
TOKEN_STEPS = [2048, 4096, 8192, 16384]

# 客户端内置重试次数（429/5xx/连接错误，指数退避）
CLIENT_MAX_RETRIES = 2

# HTTP 状态码 → 中文修复指引
_STATUS_HINTS: Dict[int, str] = {
    400: "请求参数错误：请检查图片是否损坏、prompt 是否过长",
    401: "API Key 无效或已过期：请检查 VISION_API_KEY（若 Key 带服务商前缀请确认是否要去除）",
    403: "API Key 无权限访问该模型：请检查模型是否已开通、Key 权限是否足够",
    404: "模型名或接口路径错误：请检查 VISION_MODEL 与 VISION_BASE_URL 是否正确",
    429: "触发限流：请稍后重试，或降低调用频率/调大 VISION_TIMEOUT_SECONDS",
}
_TIMEOUT_HINT = "请求超时：请检查网络连接，或调大 VISION_TIMEOUT_SECONDS"
_CONNECTION_HINT = "网络连接失败：请检查网络与 VISION_BASE_URL 是否可达"


def _status_hint(exc: Exception) -> str:
    """把异常映射为可执行的修复指引。"""
    if isinstance(exc, openai.APITimeoutError):
        return f"（超时）{_TIMEOUT_HINT}"
    if isinstance(exc, openai.APIConnectionError):
        return f"（连接失败）{_CONNECTION_HINT}"
    status = getattr(exc, "status_code", None)
    if status in _STATUS_HINTS:
        return f"（HTTP {status}）{_STATUS_HINTS[status]}"
    return ""


class OpenAICompatibleProvider(BaseVisionProvider):
    """基于 ``openai`` 客户端的 OpenAI 兼容视觉模型实现。"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 60,
        temperature: float = 0.3,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        # 某些网关要求 Authorization 为 "Bearer <key>"，openai 客户端默认即如此。
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=CLIENT_MAX_RETRIES,
        )

    def _build_messages(
        self, image_data_uris: List[str], prompt: str
    ) -> List[Dict[str, Any]]:
        """构造多模态 messages：text + 一张或多张图片。"""
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for uri in image_data_uris:
            content.append({"type": "image_url", "image_url": {"url": uri}})
        return [{"role": "user", "content": content}]

    def _extract(self, response: Any, max_tokens: int) -> Dict[str, Any]:
        """从响应中提取文本与元信息，处理截断/空内容/推理内容。"""
        choice = response.choices[0]
        message = choice.message
        text = (message.content or "").strip()
        finish = getattr(choice, "finish_reason", None)

        # 空内容诊断：截断 or 只回推理内容
        if not text:
            if finish == "length":
                raise VisionProviderError(
                    f"视觉模型输出被 max_tokens={max_tokens} 截断，且升档重试后仍无内容。"
                    "可尝试缩小图片或简化 prompt。"
                )
            reasoning = getattr(message, "reasoning_content", None)
            if reasoning:
                raise VisionProviderError(
                    "视觉模型只返回了思考内容（reasoning_content）而没有正式输出。"
                    "请更换非推理输出（non-thinking）的视觉模型，或关闭思考模式。"
                )
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
            "truncated": finish == "length",
        }

    def analyze(self, image_data_uri: str, prompt: str) -> Dict[str, Any]:
        """调用视觉模型，返回识别文本与元信息。

        返回 dict 结构：
        {
            "text": "模型返回的识别文本",
            "model": "实际使用的模型名",
            "usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...},
            "truncated": 是否被 max_tokens 截断,
        }
        """
        return self.analyze_multi([image_data_uri], prompt)

    def analyze_multi(
        self, image_data_uris: List[str], prompt: str
    ) -> Dict[str, Any]:
        """分析一张或多张图片（多图用于对比/关联分析）。"""
        last_response: Any = None
        last_max_tokens = TOKEN_STEPS[-1]
        last_error: Exception | None = None

        for max_tokens in TOKEN_STEPS:
            last_max_tokens = max_tokens
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=self._build_messages(image_data_uris, prompt),
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                )
            except Exception as exc:  # 网络错误、401、限流等统一包装
                hint = _status_hint(exc)
                raise VisionProviderError(
                    f"调用视觉模型失败（model={self.model}, base_url={self.base_url}）："
                    f"{exc}{' ' + hint if hint else ''}"
                ) from exc

            last_response = response
            try:
                outcome = self._extract(response, max_tokens)
            except VisionProviderError:
                # 仅当「因截断无内容」时才继续升档重试，其它空内容错误直接抛出
                choice = response.choices[0]
                if getattr(choice, "finish_reason", None) == "length":
                    continue
                raise

            if not outcome["truncated"]:
                return outcome
            # 有内容但被截断：升档重试，若已到最大档则返回现有结果（尽力而为）
            logger.info("输出被截断（max_tokens=%s），升档重试", max_tokens)
            time.sleep(0.3)  # 轻微退避，避免连续打满

        # 全部档位都截断：返回最后一次的非空结果
        outcome = self._extract(last_response, last_max_tokens)
        outcome["text"] += "\n\n（注意：输出较长，可能仍被截断）"
        return outcome

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
