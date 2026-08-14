"""image_utils 单元测试：本地路径 / URL / base64 / 大小限制 / 格式校验。"""

from __future__ import annotations

import base64
import re
from types import SimpleNamespace
from unittest import mock

import pytest

from deepseek_vision_mcp.image_utils import (
    ImageLoadError,
    ImageTooLargeError,
    load_image_as_base64,
)


def _data_uri_body(data_uri: str) -> bytes:
    return base64.b64decode(data_uri.split(",", 1)[1])


def _mock_public_dns(hostname="example.com", ip="93.184.216.34"):
    """mock DNS 解析为公网 IP（SSRF 校验需要）。"""
    return mock.patch(
        "deepseek_vision_mcp.image_utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", (ip, 0))],
    )


class TestLocalPath:
    def test_jpg_path_success(self, jpg_path):
        data_uri, mime = load_image_as_base64(jpg_path)
        assert mime == "image/jpeg"
        assert data_uri.startswith("data:image/jpeg;base64,")

    def test_png_path_success(self, png_path):
        data_uri, mime = load_image_as_base64(png_path)
        assert mime == "image/png"
        assert data_uri.startswith("data:image/png;base64,")

    def test_webp_path_success(self, webp_path):
        data_uri, mime = load_image_as_base64(webp_path)
        assert mime == "image/webp"
        assert data_uri.startswith("data:image/webp;base64,")

    def test_absolute_path(self, jpg_path):
        _, mime = load_image_as_base64(jpg_path)
        assert mime == "image/jpeg"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ImageLoadError, match="不存在"):
            load_image_as_base64(str(tmp_path / "nope.png"))

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ImageLoadError, match="不是文件"):
            load_image_as_base64(str(tmp_path))

    def test_non_image_file_raises(self, tmp_path):
        p = tmp_path / "note.txt"
        p.write_text("hello world")
        with pytest.raises(ImageLoadError, match="无法解析图片"):
            load_image_as_base64(str(p))


class TestUrl:
    def test_url_success(self, jpg_bytes):
        resp = SimpleNamespace(
            headers={"Content-Type": "image/jpeg"},
            content=jpg_bytes,
            raise_for_status=lambda: None,
            status_code=200,
            close=lambda: None,
        )
        with _mock_public_dns(), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", return_value=resp
        ) as m_get:
            data_uri, mime = load_image_as_base64("https://example.com/a.jpg")
        m_get.assert_called_once()
        assert mime == "image/jpeg"
        assert data_uri.startswith("data:image/jpeg;base64,")

    def test_url_without_extension_uses_magic(self, png_bytes):
        resp = SimpleNamespace(
            headers={"Content-Type": "application/octet-stream"},
            content=png_bytes,
            raise_for_status=lambda: None,
            status_code=200,
            close=lambda: None,
        )
        with _mock_public_dns(), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", return_value=resp
        ):
            _, mime = load_image_as_base64("https://example.com/photo?id=1")
        assert mime == "image/png"

    def test_url_http_error(self):
        import requests as rq

        def boom():
            raise rq.exceptions.HTTPError("403 Forbidden")

        resp = SimpleNamespace(
            headers={}, content=b"", raise_for_status=boom,
            status_code=200, close=lambda: None,
        )
        with _mock_public_dns(), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", return_value=resp
        ):
            with pytest.raises(ImageLoadError, match="下载图片失败"):
                load_image_as_base64("https://example.com/bad.jpg")

    def test_url_timeout(self):
        def boom():
            import requests as rq

            raise rq.exceptions.Timeout()

        resp = SimpleNamespace(
            headers={}, content=b"", raise_for_status=boom,
            status_code=200, close=lambda: None,
        )
        with _mock_public_dns(), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", return_value=resp
        ):
            with pytest.raises(ImageLoadError, match="超时"):
                load_image_as_base64("https://example.com/slow.jpg", download_timeout=3)


class TestSSRF:
    """URL 下载的安全防护：内网/保留地址拒绝、重定向限制。"""

    def test_private_ip_rejected(self):
        """解析到内网 IP（如 127.0.0.1 / 10.0.0.1）应被拒绝。"""
        for private_ip in ("127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254"):
            with _mock_public_dns(ip=private_ip), mock.patch(
                "deepseek_vision_mcp.image_utils.requests.get"
            ) as m_get:
                with pytest.raises(ImageLoadError, match="拒绝访问"):
                    load_image_as_base64("https://example.com/a.jpg")
            m_get.assert_not_called()

    def test_mixed_ips_rejected(self):
        """同时解析出公网与内网 IP（DNS rebinding 场景）应被拒绝。"""
        with mock.patch(
            "deepseek_vision_mcp.image_utils.socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("93.184.216.34", 0)),
                (2, 1, 6, "", ("10.0.0.5", 0)),
            ],
        ), mock.patch("deepseek_vision_mcp.image_utils.requests.get") as m_get:
            with pytest.raises(ImageLoadError, match="拒绝访问"):
                load_image_as_base64("https://example.com/a.jpg")
        m_get.assert_not_called()

    def test_localhost_hostname_rejected(self):
        with mock.patch("deepseek_vision_mcp.image_utils.requests.get") as m_get:
            with pytest.raises(ImageLoadError, match="拒绝访问"):
                load_image_as_base64("http://localhost:8080/a.jpg")
        m_get.assert_not_called()

    def test_allow_private_flag_bypasses(self, jpg_bytes):
        """显式允许内网地址时可下载。"""
        resp = SimpleNamespace(
            headers={"Content-Type": "image/jpeg"},
            content=jpg_bytes,
            raise_for_status=lambda: None,
            status_code=200,
            close=lambda: None,
        )
        with _mock_public_dns(ip="10.0.0.5"), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", return_value=resp
        ):
            data_uri, mime = load_image_as_base64(
                "https://example.com/a.jpg", allow_private=True
            )
        assert mime == "image/jpeg"

    def test_redirect_each_hop_revalidated(self, jpg_bytes):
        """重定向的每一跳都要重新做 SSRF 校验。"""
        resp_ok = SimpleNamespace(
            headers={"Content-Type": "image/jpeg"},
            content=jpg_bytes,
            raise_for_status=lambda: None,
            status_code=200,
            close=lambda: None,
        )

        def fake_get(url, **kwargs):
            if "first" in url:
                return SimpleNamespace(
                    headers={"Location": "https://example.com/second.jpg"},
                    content=b"",
                    raise_for_status=lambda: None,
                    status_code=302,
                    close=lambda: None,
                )
            return resp_ok

        with _mock_public_dns(), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", side_effect=fake_get
        ) as m_get:
            data_uri, mime = load_image_as_base64("https://example.com/first.jpg")
        assert mime == "image/jpeg"
        assert m_get.call_count == 2  # 第一跳 302 + 第二跳成功

    def test_redirect_to_private_rejected(self, jpg_bytes):
        """重定向目标解析到内网 IP 应被拒绝。"""
        redirect_resp = SimpleNamespace(
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
            content=b"",
            raise_for_status=lambda: None,
            status_code=302,
            close=lambda: None,
        )
        # 第一跳 example.com 公网；第二跳目标主机名是 IP 字面量 → 直接命中私网校验
        with _mock_public_dns(), mock.patch(
            "deepseek_vision_mcp.image_utils.requests.get", return_value=redirect_resp
        ):
            with pytest.raises(ImageLoadError, match="拒绝访问"):
                load_image_as_base64("https://example.com/redir")


class TestBase64:
    def test_raw_base64(self, jpg_base64):
        data_uri, mime = load_image_as_base64(jpg_base64)
        assert mime == "image/jpeg"
        assert data_uri.startswith("data:image/jpeg;base64,")

    def test_data_uri_with_prefix(self, jpg_data_uri):
        data_uri, mime = load_image_as_base64(jpg_data_uri)
        assert mime == "image/jpeg"
        assert data_uri == jpg_data_uri

    def test_base64_with_whitespace(self, jpg_base64):
        spaced = jpg_base64[:10] + "\n" + jpg_base64[10:20] + " " + jpg_base64[20:]
        data_uri, mime = load_image_as_base64(spaced)
        assert mime == "image/jpeg"

    def test_garbage_string_raises(self):
        with pytest.raises(ImageLoadError):
            load_image_as_base64("这不是一张图片也不是路径")

    def test_empty_raises(self):
        with pytest.raises(ImageLoadError, match="为空"):
            load_image_as_base64("   ")


class TestSizeLimit:
    def test_oversize_gets_compressed(self, tmp_path):
        """构造一张超过 10KB 限制的图片，应被压缩到限制以内。"""
        from PIL import Image

        img = Image.new("RGB", (900, 900), (30, 90, 200))
        p = tmp_path / "big.jpg"
        img.save(p, format="JPEG", quality=95)
        assert p.stat().st_size > 10 * 1024

        data_uri, mime = load_image_as_base64(str(p), max_size_kb=10)
        assert len(_data_uri_body(data_uri)) <= 10 * 1024
        assert mime in ("image/jpeg", "image/webp")

    def test_within_limit_not_reencoded(self, jpg_path, jpg_bytes):
        data_uri, mime = load_image_as_base64(jpg_path, max_size_kb=2048)
        assert mime == "image/jpeg"

    def test_no_compress_flag_raises(self, tmp_path):
        from PIL import Image

        p = tmp_path / "big.jpg"
        img = Image.new("RGB", (900, 900), (30, 90, 200))
        img.save(p, format="JPEG", quality=95)
        with pytest.raises(ImageTooLargeError, match="超过限制"):
            load_image_as_base64(str(p), max_size_kb=10, allow_compress=False)

    def test_tiny_limit_eventually_raises(self, tmp_path):
        """极端小的限制：压缩到极限仍超限时应抛 ImageTooLargeError。

        使用随机噪声图（压缩率极低），确保即使缩到最小尺寸仍无法达标。
        """
        import os

        from PIL import Image

        size = (800, 800)
        noise = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
        p = tmp_path / "noise.png"
        noise.save(p, format="PNG")
        with pytest.raises(ImageTooLargeError):
            load_image_as_base64(str(p), max_size_kb=1)


class TestFormatValidation:
    def test_disallowed_format(self, tmp_path):
        from PIL import Image

        p = tmp_path / "a.bmp"
        Image.new("RGB", (16, 16), (1, 2, 3)).save(p, format="BMP")
        with pytest.raises(ImageLoadError, match="不支持的图片格式"):
            load_image_as_base64(str(p))

    def test_allowed_formats_override(self, tmp_path):
        from PIL import Image

        p = tmp_path / "a.bmp"
        Image.new("RGB", (16, 16), (1, 2, 3)).save(p, format="BMP")
        # 把 bmp 加入允许列表后应能通过（Pillow 会按真实格式编码）
        data_uri, mime = load_image_as_base64(
            str(p), allowed_formats=["jpg", "jpeg", "png", "webp", "bmp"]
        )
        assert data_uri.startswith("data:image/bmp;base64,")
