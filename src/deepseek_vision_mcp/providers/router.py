"""跨服务商视觉路由、共享重试预算与短期熔断。"""

from __future__ import annotations

import threading
import time
from typing import Any

from .base import BaseVisionProvider, VisionProviderError
from .openai_compatible import AttemptBudget, OpenAICompatibleProvider

_CIRCUITS: dict[str, float] = {}
_CIRCUIT_LOCK = threading.Lock()
_CIRCUIT_STATUSES = {429, 500, 502, 503, 504}


def _circuit_key(endpoint: dict[str, Any]) -> str:
    return f"{endpoint['id']}|{endpoint['base_url']}|{endpoint['model']}"


class FallbackVisionProvider(BaseVisionProvider):
    """按优先级尝试主服务与备用服务，所有请求共享总预算。"""

    def __init__(self, config: Any) -> None:
        self.budget = AttemptBudget(getattr(config, "max_attempts", 4))
        self.cooldown_seconds = getattr(config, "circuit_cooldown_seconds", 90)
        primary = {
            "id": getattr(config, "service_id", "primary"),
            "api_key": config.api_key,
            "api_keys": getattr(config, "api_keys", [config.api_key]),
            "model": config.model,
            "models": getattr(config, "models", [config.model]),
            "base_url": config.base_url,
        }
        self.endpoints = [primary, *getattr(config, "fallback_endpoints", [])]
        self.providers = [
            OpenAICompatibleProvider(
                api_key=endpoint["api_key"],
                api_keys=endpoint.get("api_keys"),
                model=endpoint["model"],
                models=endpoint.get("models"),
                base_url=endpoint["base_url"],
                timeout_seconds=config.timeout_seconds,
                temperature=getattr(config, "temperature", 0.3),
                attempt_budget=self.budget,
            )
            for endpoint in self.endpoints
        ]

    def _open_for(self, endpoint: dict[str, Any]) -> float:
        now = time.monotonic()
        with _CIRCUIT_LOCK:
            until = _CIRCUITS.get(_circuit_key(endpoint), 0.0)
            if until and until <= now:
                _CIRCUITS.pop(_circuit_key(endpoint), None)
                return 0.0
            return max(0.0, until - now)

    def _mark_failure(self, endpoint: dict[str, Any], status: int | None) -> None:
        # 熔断的价值是让下一次调用绕过已知故障节点、直达备用服务。
        # 单服务场景不熔断，否则用户稍后手动重试也会被本地直接拒绝。
        if len(self.endpoints) < 2 or status not in _CIRCUIT_STATUSES:
            return
        with _CIRCUIT_LOCK:
            _CIRCUITS[_circuit_key(endpoint)] = time.monotonic() + self.cooldown_seconds

    def _mark_success(self, endpoint: dict[str, Any]) -> None:
        with _CIRCUIT_LOCK:
            _CIRCUITS.pop(_circuit_key(endpoint), None)

    def analyze(self, image_data_uri: str, prompt: str) -> dict[str, Any]:
        return self.analyze_multi([image_data_uri], prompt)

    def analyze_multi(
        self, image_data_uris: list[str], prompt: str
    ) -> dict[str, Any]:
        failures: list[str] = []
        open_waits: list[float] = []
        for index, (endpoint, provider) in enumerate(zip(self.endpoints, self.providers)):
            wait = self._open_for(endpoint)
            if wait > 0:
                open_waits.append(wait)
                failures.append(f"{endpoint['id']} 熔断中（约 {int(wait) + 1} 秒）")
                continue
            try:
                outcome = provider.analyze_multi(image_data_uris, prompt)
                self._mark_success(endpoint)
                outcome.update(
                    {
                        "provider": endpoint["id"],
                        "fallback_used": index > 0,
                        "attempts": self.budget.attempts,
                    }
                )
                return outcome
            except VisionProviderError as exc:
                status = getattr(exc, "status_code", None)
                self._mark_failure(endpoint, status)
                failures.append(f"{endpoint['id']}: {exc}")
                if self.budget.remaining <= 0:
                    break

        if open_waits and len(open_waits) == len(self.endpoints):
            wait = int(min(open_waits)) + 1
            raise VisionProviderError(f"所有视觉服务暂时熔断，请约 {wait} 秒后再试")
        detail = "；".join(failures) or "没有可用的视觉服务"
        raise VisionProviderError(
            f"视觉服务链全部失败（已请求 {self.budget.attempts}/{self.budget.maximum} 次）：{detail}"
        )

    def close(self) -> None:
        for provider in self.providers:
            provider.close()
