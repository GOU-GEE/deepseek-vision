"""图片加载、校验、压缩与 base64 编码。

``analyze_image`` 工具接收三种输入形式：
- 本地文件路径（如 ``./screenshot.png``、绝对路径）
- http/https URL
- 纯 base64 字符串（可带 ``data:`` URI 前缀，也可不带）

统一出口：:func:`load_image_as_base64` 返回 ``(data_uri, mime)``，
其中 ``data_uri`` 形如 ``data:image/jpeg;base64,....``。
"""

from __future__ import annotations

import base64
import io
import ipaddress
import mimetypes
import re
import socket
from pathlib import Path
from typing import Tuple
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageOps

# 允许的图片格式（与 MIME 类型映射）
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
EXTENSION_TO_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
MIME_TO_EXTENSION = {v: k for k, v in EXTENSION_TO_MIME.items()}

# 匹配带前缀的 base64 data URI，例如 data:image/png;base64,iVBOR...
_DATA_URI_RE = re.compile(
    r"^data:(?P<mime>[\w.+-]+/[\w.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$"
)
# 匹配纯 base64 字符串（可能包含换行/空白）
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")

# 常见图片文件头 -> MIME 类型
_MAGIC_MIME = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # RIFF....WEBP
}


class ImageLoadError(Exception):
    """图片加载/处理失败。"""


class ImageTooLargeError(ImageLoadError):
    """图片即使压缩后仍然超过大小限制。"""


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _looks_like_data_uri(value: str) -> bool:
    return value.startswith("data:") and ";base64," in value[:64]


def _looks_like_base64(value: str) -> bool:
    """判断字符串是否像纯 base64（图片数据通常以常见文件头开头）。"""
    if len(value) < 32:
        return False
    # 去掉空白后必须是合法 base64 字符集
    compact = re.sub(r"\s+", "", value)
    if not _BASE64_RE.match(compact):
        return False
    # 用文件头魔数进一步确认是图片
    try:
        raw = base64.b64decode(compact)
    except Exception:
        return False
    return any(raw.startswith(magic) for magic in _MAGIC_MIME)


def guess_mime_from_bytes(raw: bytes) -> str:
    """根据文件头魔数猜测 MIME 类型。"""
    for magic, mime in _MAGIC_MIME.items():
        if raw.startswith(magic):
            # RIFF 需要进一步确认 WEBP 标记
            if magic == b"RIFF" and not raw[8:12] == b"WEBP":
                continue
            return mime
    return ""


# ---------------------------------------------------------------------------
# SSRF 防护（借鉴 image-vision-mcp / staticdeng）：
# 下载 URL 前校验解析出的 IP，拒绝私网/回环/链路本地等内网地址，
# 防止恶意 URL 探测内网服务或云元数据（169.254.169.254 等）。
# ---------------------------------------------------------------------------
# 始终拒绝的主机名（含常见云元数据端点）
_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata",
    "metadata.google.internal",
    "metadata.google",
    "instance-data",
    "instance-data.ec2.internal",
}

# 单次下载最大字节数（防御性上限，压缩逻辑在读取后处理）
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
# 重定向最多跟随次数（每跳都重新做 SSRF 校验）
_MAX_REDIRECTS = 5


def _is_blocked_ip(ip_str: str) -> bool:
    """判断 IP 是否属于内网/保留/元数据地址。"""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # 无法解析的 IP 一律拒绝
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _assert_public_host(hostname: str, allow_private: bool = False) -> None:
    """校验主机名解析出的所有 IP 均为公网地址；含内网地址则拒绝。

    只信任「当前解析结果全部为公网」的主机，并在每次重定向时重新校验，
    可拒绝混合公网/内网解析结果并降低 DNS rebinding 风险。
    """
    if allow_private:
        return
    host = hostname.strip().lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".local"):
        raise ImageLoadError(f"出于安全考虑，拒绝访问内网/保留地址：{hostname}")
    # 兼容 IPv6 字面量 [::1]
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    # 主机名本身是 IP 字面量（如 http://169.254.169.254/）→ 直接校验，不走 DNS
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if _is_blocked_ip(str(literal_ip)):
            raise ImageLoadError(
                f"出于安全考虑，拒绝访问内网/保留地址（{hostname}）。"
            )
        return
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ImageLoadError(f"无法解析图片 URL 的主机名：{hostname}") from exc
    if not infos:
        raise ImageLoadError(f"无法解析图片 URL 的主机名：{hostname}")
    ips = {info[4][0] for info in infos}
    blocked = [ip for ip in ips if _is_blocked_ip(ip)]
    if blocked:
        raise ImageLoadError(
            f"出于安全考虑，拒绝访问内网/保留地址（{hostname} 解析到 {', '.join(blocked)}）。"
        )


def _download_from_url(url: str, timeout: int, allow_private: bool = False) -> bytes:
    """下载 URL 图片，带超时、SSRF 防护与重定向限制。"""
    current = url
    parsed_label = urlparse(url)
    safe_url = f"{parsed_label.scheme}://{parsed_label.hostname or ''}{parsed_label.path}"
    for _ in range(_MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        if parsed.scheme not in ("http", "https"):
            raise ImageLoadError(f"不支持的 URL 协议：{parsed.scheme}")
        _assert_public_host(parsed.hostname or "", allow_private)

        try:
            resp = requests.get(
                current, timeout=timeout, stream=True, allow_redirects=False
            )
        except requests.exceptions.Timeout as exc:
            raise ImageLoadError(f"下载图片超时（{timeout}s）：{safe_url}") from exc
        except requests.exceptions.RequestException as exc:
            raise ImageLoadError(
                f"下载图片失败：{safe_url}（{type(exc).__name__}）"
            ) from exc

        # 手动跟随重定向（每跳重新做 SSRF 校验）
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                raise ImageLoadError(f"重定向响应缺少 Location：{safe_url}")
            current = urljoin(current, location)
            continue

        try:
            resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            resp.close()
            raise ImageLoadError(f"下载图片超时（{timeout}s）：{safe_url}") from exc
        except requests.exceptions.RequestException as exc:
            resp.close()
            raise ImageLoadError(
                f"下载图片失败：{safe_url}（HTTP {resp.status_code}）"
            ) from exc

        content_length = resp.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > _MAX_DOWNLOAD_BYTES:
                    resp.close()
                    raise ImageLoadError(
                        f"图片超过下载上限（{_MAX_DOWNLOAD_BYTES // 1024 // 1024} MB）：{safe_url}"
                    )
            except ValueError:
                pass

        # 必须逐块读取并边读边限流；resp.content 会先把任意大响应全部载入内存。
        chunks = bytearray()
        try:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                chunks.extend(chunk)
                if len(chunks) > _MAX_DOWNLOAD_BYTES:
                    raise ImageTooLargeError(
                        f"图片超过下载上限（{_MAX_DOWNLOAD_BYTES // 1024 // 1024} MB）：{safe_url}"
                    )
        except requests.exceptions.RequestException as exc:
            raise ImageLoadError(
                f"下载图片失败：{safe_url}（{type(exc).__name__}）"
            ) from exc
        finally:
            resp.close()
        raw = bytes(chunks)
        if not raw:
            raise ImageLoadError(f"下载到的图片内容为空：{safe_url}")
        return raw
    raise ImageLoadError(f"图片 URL 重定向次数过多（>{_MAX_REDIRECTS}）：{safe_url}")


# 本地文件读取前的硬性大小上限（防超大文件整读进内存；之后压缩会进一步处理）
_MAX_LOCAL_READ_BYTES = 50 * 1024 * 1024


def _read_local_file(path: str) -> bytes:
    p = Path(path)
    if not p.exists():
        raise ImageLoadError(f"图片文件不存在：{path}")
    if not p.is_file():
        raise ImageLoadError(f"路径不是文件：{path}")
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise ImageLoadError(f"读取图片文件信息失败：{path}（{exc}）") from exc
    if size > _MAX_LOCAL_READ_BYTES:
        raise ImageLoadError(
            f"图片文件过大（{size / 1024 / 1024:.0f} MB，上限 {_MAX_LOCAL_READ_BYTES // 1024 // 1024} MB）：{path}"
        )
    try:
        return p.read_bytes()
    except OSError as exc:
        raise ImageLoadError(f"读取图片文件失败：{path}（{exc}）") from exc


def _load_raw(
    image: str, download_timeout: int, allow_private: bool = False
) -> Tuple[bytes, str, str]:
    """把输入归一化为 (原始字节, MIME, 来源描述)。

    返回的 MIME 为空时表示未知，需要调用方探测。
    """
    value = image.strip()
    if not value:
        raise ImageLoadError("图片参数为空，请提供本地路径、URL 或 base64 字符串。")

    # 1) data URI
    if _looks_like_data_uri(value):
        m = _DATA_URI_RE.match(value)
        if not m:
            raise ImageLoadError("data URI 格式无效，应为 data:<mime>;base64,<数据>。")
        try:
            raw = base64.b64decode(re.sub(r"\s+", "", m.group("data")))
        except Exception as exc:
            raise ImageLoadError("data URI 中的 base64 数据无法解码。") from exc
        return raw, m.group("mime").lower(), "data URI"

    # 2) URL
    if _looks_like_url(value):
        raw = _download_from_url(value, download_timeout, allow_private)
        mime = guess_mime_from_bytes(raw)
        if not mime:
            # 回退：根据 URL 后缀猜测
            ext = Path(urlparse(value).path).suffix.lower().lstrip(".")
            mime = EXTENSION_TO_MIME.get(ext, "")
        return raw, mime, "URL"

    # 3) 本地文件路径
    if not _looks_like_base64(value):
        raw = _read_local_file(value)
        ext = Path(value).suffix.lower().lstrip(".")
        mime = EXTENSION_TO_MIME.get(ext, "")
        if not mime:
            mime = guess_mime_from_bytes(raw)
        return raw, mime, "本地文件"

    # 4) 纯 base64
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", value))
    except Exception as exc:
        raise ImageLoadError("输入既不是有效路径/URL，也不是有效的 base64 图片数据。") from exc
    mime = guess_mime_from_bytes(raw)
    return raw, mime, "base64"


def _verify_and_normalize(
    raw: bytes, mime: str, allowed_formats: list[str]
) -> Tuple[bytes, str]:
    """校验格式，必要时用 Pillow 转码为标准格式（jpeg/png/webp）。"""
    if not raw:
        raise ImageLoadError("图片数据为空。")

    # 允许列表校验
    allowed = set(allowed_formats) or ALLOWED_EXTENSIONS
    if mime and mime in MIME_TO_EXTENSION and MIME_TO_EXTENSION[mime] in allowed:
        return raw, mime

    # 让 Pillow 判断真实格式
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = (img.format or "").lower()
    except Exception as exc:
        raise ImageLoadError("无法解析图片，仅支持 jpg/jpeg/png/webp 格式。") from exc

    if fmt not in allowed:
        raise ImageLoadError(
            f"不支持的图片格式：{fmt or '未知'}。允许的格式：{', '.join(sorted(allowed))}"
        )
    # 内置映射优先；其余交给 mimetypes 猜测（如 bmp -> image/bmp）
    mapped = EXTENSION_TO_MIME.get(fmt)
    if not mapped:
        mapped = mimetypes.guess_type(f"x.{fmt}")[0] or "image/jpeg"
    return raw, mapped


def _compress(raw: bytes, mime: str, max_size_kb: int) -> Tuple[bytes, str]:
    """把图片压缩到 max_size_kb 以内。

    策略：依次降低 JPEG/WebP 质量；若质量降到最低仍超限，则缩小分辨率
    （每次边长减半）。返回压缩后的 (bytes, mime)。
    """
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "P", "LA"):
        # 透明图保持 PNG，否则转 RGB 以支持 JPEG 压缩
        if mime == "image/png" and "A" in img.getbands():
            return _compress_png(img, max_size_kb)
        img = img.convert("RGB")
    else:
        img = img.convert("RGB")

    target_bytes = max_size_kb * 1024

    # 1) 先试质量压缩
    for quality in (85, 70, 55, 40, 25):
        out = io.BytesIO()
        if mime == "image/webp":
            img.save(out, format="WEBP", quality=quality)
        else:
            img.save(out, format="JPEG", quality=quality)
        if out.tell() <= target_bytes:
            new_mime = "image/webp" if mime == "image/webp" else "image/jpeg"
            return out.getvalue(), new_mime

    # 2) 质量不够则缩小分辨率（不低于 128px，避免识别质量过差）
    while img.width > 128 and img.height > 128:
        img = img.resize(
            (max(1, img.width // 2), max(1, img.height // 2)),
            Image.LANCZOS,
        )
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=60)
        if out.tell() <= target_bytes:
            return out.getvalue(), "image/jpeg"

    raise ImageTooLargeError(
        f"图片压缩后仍超过大小限制（{max_size_kb} KB），请更换更小的图片。"
    )


def _compress_png(img: Image.Image, max_size_kb: int) -> Tuple[bytes, str]:
    """对带透明通道的 PNG 尝试优化（调色板化 + 无损优化）。"""
    target_bytes = max_size_kb * 1024
    out = io.BytesIO()
    try:
        quantized = img.quantize(colors=256, method=Image.MEDIANCUT)
        quantized.save(out, format="PNG", optimize=True)
    except Exception:
        img.save(out, format="PNG", optimize=True)
    if out.tell() <= target_bytes:
        return out.getvalue(), "image/png"
    # 仍超限：丢弃透明通道转 JPEG
    rgb = img.convert("RGB")
    out2 = io.BytesIO()
    rgb.save(out2, format="JPEG", quality=70)
    if out2.tell() <= target_bytes:
        return out2.getvalue(), "image/jpeg"
    raise ImageTooLargeError(
        f"图片压缩后仍超过大小限制（{max_size_kb} KB），请更换更小的图片。"
    )


def load_image_as_base64(
    image: str,
    *,
    max_size_kb: int = 2048,
    download_timeout: int = 30,
    allowed_formats: list[str] | None = None,
    allow_compress: bool = True,
    allow_private: bool = False,
) -> Tuple[str, str]:
    """加载任意形式的图片输入，返回 (data URI, MIME)。

    参数:
        image: 本地路径 / http(s) URL / base64 字符串 / data URI。
        max_size_kb: 大小限制（KB），超限时尝试压缩。
        download_timeout: URL 下载超时（秒）。
        allowed_formats: 允许的格式扩展名列表。
        allow_compress: 超限时是否允许压缩，False 则直接抛错。
        allow_private: 是否允许下载内网/保留地址的 URL（默认拒绝，SSRF 防护）。

    返回:
        (data_uri, mime)，data_uri 形如 ``data:image/jpeg;base64,....``。

    异常:
        ImageLoadError: 无法加载/解析/编码。
        ImageTooLargeError: 压缩后仍超限（ImageLoadError 子类）。
    """
    raw, mime, source = _load_raw(image, download_timeout, allow_private)
    raw, mime = _verify_and_normalize(raw, mime, allowed_formats or [])

    size_kb = len(raw) / 1024
    if size_kb > max_size_kb:
        if not allow_compress:
            raise ImageTooLargeError(
                f"图片大小 {size_kb:.0f} KB 超过限制 {max_size_kb} KB（来源：{source}）。"
            )
        raw, mime = _compress(raw, mime, max_size_kb)

    b64 = base64.b64encode(raw).decode("ascii")
    data_uri = f"data:{mime};base64,{b64}"
    return data_uri, mime
