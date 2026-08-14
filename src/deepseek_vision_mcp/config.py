"""配置加载模块。

配置优先级（高 -> 低）：
1. 进程环境变量（``VISION_*``）
2. 项目根目录 / 当前目录下的 ``.env`` 文件
3. ``config.json`` 文件（若存在）
4. 内置默认值

所有配置项均以 ``VISION_`` 前缀命名，便于与主模型配置区分。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# 项目根目录（包所在目录的上级的上级，即仓库根）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# 默认值
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Any] = {
    # 视觉模型 API Key（无默认值，必须由用户配置）
    "VISION_API_KEY": "",
    # 模型名称（默认智谱 glm-4.6v-flash：GLM-4.6V 免费版，免费视觉模型里效果最好）
    "VISION_MODEL": "glm-4.6v-flash",
    # OpenAI 兼容 API 基础 URL（默认指向智谱 AI）
    "VISION_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
    # 图片大小限制（KB），超过会尝试压缩，压缩后仍超限则报错
    "VISION_MAX_IMAGE_SIZE_KB": 2048,
    # 请求超时时间（秒）
    "VISION_TIMEOUT_SECONDS": 60,
    # 视觉模型采样温度（0-2；0.3 更适合 OCR/报错诊断等确定性任务）
    "VISION_TEMPERATURE": 0.3,
    # 允许的图片格式
    "VISION_ALLOWED_FORMATS": "jpg,jpeg,png,webp",
    # 从 URL 下载图片的超时（秒）
    "VISION_DOWNLOAD_TIMEOUT_SECONDS": 30,
    # 是否允许下载内网/保留地址的 URL（默认 false，SSRF 防护；自建内网服务时设为 true）
    "VISION_ALLOW_PRIVATE_IMAGE_URLS": "false",
    # 是否从 config.json 加载（默认开启）
    "VISION_USE_CONFIG_FILE": "true",
    # config.json 路径（默认为项目根目录下的 config.json）
    "VISION_CONFIG_FILE": "",
    # 预留：服务商特殊接口格式的扩展名（本版本仅实现 openai_compatible）
    "VISION_PROVIDER": "openai_compatible",
}

# 可解析为布尔值的字符串
_TRUE_VALUES = {"1", "true", "yes", "on", "y"}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in _TRUE_VALUES


@dataclass
class VisionConfig:
    """解析后的视觉配置。"""

    api_key: str
    model: str
    base_url: str
    max_image_size_kb: int
    timeout_seconds: int
    temperature: float
    allowed_formats: list[str]
    download_timeout_seconds: int
    allow_private_urls: bool
    use_config_file: bool
    config_file: Path
    provider: str
    # 保留所有原始配置项，便于排查与扩展
    raw: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """校验配置的合法性，非法配置抛出 ValueError。"""
        if not self.api_key:
            raise ValueError(
                "缺少 VISION_API_KEY。请通过环境变量、.env 文件或 config.json 配置，"
                "详见 README.md 的『快速开始』章节。"
            )
        if not self.model:
            raise ValueError("VISION_MODEL 不能为空。")
        if not self.base_url:
            raise ValueError("VISION_BASE_URL 不能为空。")
        if self.max_image_size_kb <= 0:
            raise ValueError("VISION_MAX_IMAGE_SIZE_KB 必须为正整数。")
        if self.timeout_seconds <= 0:
            raise ValueError("VISION_TIMEOUT_SECONDS 必须为正整数。")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("VISION_TEMPERATURE 必须在 0 到 2 之间。")
        if self.download_timeout_seconds <= 0:
            raise ValueError("VISION_DOWNLOAD_TIMEOUT_SECONDS 必须为正整数。")


def _load_config_json(path: Path) -> Dict[str, Any]:
    """读取 config.json，把顶层键视为配置项（兼容带嵌套的写法）。"""
    if not path.exists() or path.is_dir():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    # 支持 {"vision": {...}} 的嵌套写法，也支持 {"VISION_API_KEY": "..."} 的扁平写法；
    # 键名大小写不敏感（api_key == API_KEY == ApiKey）。
    nested = data.get("vision", {}) if isinstance(data.get("vision"), dict) else {}
    flat = {k: v for k, v in data.items() if k != "vision"}
    merged: Dict[str, Any] = {}
    for key, value in {**flat, **nested}.items():
        normalized = key.strip().upper()
        merged[normalized if normalized.startswith("VISION_") else f"VISION_{normalized}"] = value
    return merged


def load_config(
    env: Optional[Dict[str, str]] = None,
    config_path: Optional[Path] = None,
    *,
    validate: bool = True,
) -> VisionConfig:
    """按优先级加载配置。

    参数:
        env: 显式传入的环境变量（测试用），None 时使用 os.environ。
        config_path: 显式指定 config.json 路径，None 时按默认规则查找。
        validate: 是否执行校验（测试时可关闭）。

    返回:
        VisionConfig 配置对象。
    """
    # 1) 加载 .env 文件（仅当 os.environ 未设置对应变量时才生效）
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        load_dotenv(Path.cwd() / ".env")

    environment = env if env is not None else os.environ

    # 2) 确定 config.json 路径（空值表示不使用配置文件）
    if not config_path:
        config_path = Path(
            environment.get("VISION_CONFIG_FILE") or PROJECT_ROOT / "config.json"
        )
    config_path = Path(config_path)

    # 3) 合并：默认值 < config.json < .env/环境变量
    merged: Dict[str, Any] = dict(DEFAULTS)
    use_config_file = _to_bool(environment.get("VISION_USE_CONFIG_FILE", "true"))
    if use_config_file:
        merged.update(_load_config_json(config_path))
    for key in DEFAULTS:
        if key in environment and environment[key] != "":
            merged[key] = environment[key]

    cfg = VisionConfig(
        api_key=str(merged["VISION_API_KEY"]),
        model=str(merged["VISION_MODEL"]),
        base_url=str(merged["VISION_BASE_URL"]).rstrip("/"),
        max_image_size_kb=int(merged["VISION_MAX_IMAGE_SIZE_KB"]),
        timeout_seconds=int(merged["VISION_TIMEOUT_SECONDS"]),
        temperature=float(merged["VISION_TEMPERATURE"]),
        allowed_formats=[
            f.strip().lower()
            for f in str(merged["VISION_ALLOWED_FORMATS"]).split(",")
            if f.strip()
        ],
        download_timeout_seconds=int(merged["VISION_DOWNLOAD_TIMEOUT_SECONDS"]),
        allow_private_urls=_to_bool(merged["VISION_ALLOW_PRIVATE_IMAGE_URLS"]),
        use_config_file=use_config_file,
        config_file=config_path,
        provider=str(merged["VISION_PROVIDER"]).strip().lower(),
        raw=merged,
    )
    if validate:
        cfg.validate()
    return cfg
