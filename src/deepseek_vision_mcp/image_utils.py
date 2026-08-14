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
import mimetypes
import re
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

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


def _download_from_url(url: str, timeout: int) -> bytes:
    """下载 URL 图片，带超时与错误处理。"""
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise ImageLoadError(f"下载图片超时（{timeout}s）：{url}") from exc
    except requests.exceptions.RequestException as exc:
        raise ImageLoadError(f"下载图片失败：{url}（{exc}）") from exc

    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    raw = resp.content
    if not raw:
        raise ImageLoadError(f"下载到的图片内容为空：{url}")
    return raw


def _read_local_file(path: str) -> bytes:
    p = Path(path)
    if not p.exists():
        raise ImageLoadError(f"图片文件不存在：{path}")
    if not p.is_file():
        raise ImageLoadError(f"路径不是文件：{path}")
    try:
        return p.read_bytes()
    except OSError as exc:
        raise ImageLoadError(f"读取图片文件失败：{path}（{exc}）") from exc


def _load_raw(image: str, download_timeout: int) -> Tuple[bytes, str, str]:
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
        raw = _download_from_url(value, download_timeout)
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
) -> Tuple[str, str]:
    """加载任意形式的图片输入，返回 (data URI, MIME)。

    参数:
        image: 本地路径 / http(s) URL / base64 字符串 / data URI。
        max_size_kb: 大小限制（KB），超限时尝试压缩。
        download_timeout: URL 下载超时（秒）。
        allowed_formats: 允许的格式扩展名列表。
        allow_compress: 超限时是否允许压缩，False 则直接抛错。

    返回:
        (data_uri, mime)，data_uri 形如 ``data:image/jpeg;base64,....``。

    异常:
        ImageLoadError: 无法加载/解析/编码。
        ImageTooLargeError: 压缩后仍超限（ImageLoadError 子类）。
    """
    raw, mime, source = _load_raw(image, download_timeout)
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
