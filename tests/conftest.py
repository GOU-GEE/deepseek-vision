"""pytest 共享夹具：生成测试图片与配置。"""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from deepseek_vision_mcp.config import VisionConfig


def _make_image_bytes(fmt: str, size: tuple = (64, 48)) -> bytes:
    """生成一张纯色测试图。"""
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 80, 200)).save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture(scope="session")
def jpg_bytes() -> bytes:
    return _make_image_bytes("JPEG")


@pytest.fixture(scope="session")
def png_bytes() -> bytes:
    return _make_image_bytes("PNG")


@pytest.fixture(scope="session")
def webp_bytes() -> bytes:
    return _make_image_bytes("WEBP")


@pytest.fixture()
def jpg_path(tmp_path, jpg_bytes) -> str:
    p = tmp_path / "sample.jpg"
    p.write_bytes(jpg_bytes)
    return str(p)


@pytest.fixture()
def png_path(tmp_path, png_bytes) -> str:
    p = tmp_path / "sample.png"
    p.write_bytes(png_bytes)
    return str(p)


@pytest.fixture()
def webp_path(tmp_path, webp_bytes) -> str:
    p = tmp_path / "sample.webp"
    p.write_bytes(webp_bytes)
    return str(p)


@pytest.fixture()
def jpg_base64(jpg_bytes) -> str:
    return base64.b64encode(jpg_bytes).decode("ascii")


@pytest.fixture()
def jpg_data_uri(jpg_base64) -> str:
    return f"data:image/jpeg;base64,{jpg_base64}"


def make_config(**overrides) -> VisionConfig:
    """构造一个可用的测试配置（默认带假 API Key）。"""
    defaults = {
        "api_key": "test-key",
        "api_keys": ["test-key"],
        "model": "glm-4.6v-flash",
        "models": ["glm-4.6v-flash"],
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "max_image_size_kb": 2048,
        "timeout_seconds": 60,
        "temperature": 0.3,
        "download_timeout_seconds": 30,
        "allow_private_urls": False,
        "allowed_formats": ["jpg", "jpeg", "png", "webp"],
        "provider": "openai_compatible",
        "service_id": "zhipu",
        "use_config_file": False,
        "cache_enabled": True,
        "cache_max_entries": 128,
        "cache_ttl_seconds": 3600,
    }
    defaults.update(overrides)
    return VisionConfig(config_file="", raw=defaults, **defaults)


@pytest.fixture()
def vision_config() -> VisionConfig:
    return make_config()
