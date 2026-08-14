"""跨平台剪贴板图片提取（借鉴 deepseek-eyes 的实现思路）。

平台支持：
- Windows: PIL ``ImageGrab``（原生）
- macOS:   PIL ``ImageGrab``，失败时回退到 ``pngpaste``
- Linux:   ``wl-paste``（Wayland）或 ``xclip``（X11）

临时文件优先写入项目本地目录，避免 Windows 中文用户名路径的编码问题。
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

# 项目根目录（src/ 的上级）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ClipboardError(RuntimeError):
    """无法从剪贴板读取图片时抛出。"""


def _temp_path() -> Path:
    candidates = [
        _PROJECT_ROOT / "tmp",
        Path(tempfile.gettempdir()) / "deepseek_vision_mcp",
    ]
    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d / f"clip_{uuid.uuid4().hex}.png"
        except (OSError, UnicodeError):
            continue
    raise ClipboardError("无法创建临时目录。")


def save_clipboard_image() -> str:
    """把剪贴板中的图片保存为临时 PNG，返回其路径。

    剪贴板中没有图片时抛出 :class:`ClipboardError`。
    """
    out = _temp_path()
    platform = sys.platform

    if platform == "win32":
        _grab_with_pil(out)
    elif platform == "darwin":
        try:
            _grab_with_pil(out)
        except ClipboardError:
            _grab_macos_pngpaste(out)
    else:
        _grab_linux(out)

    if not out.exists() or out.stat().st_size == 0:
        raise ClipboardError("剪贴板中没有图片。")
    return str(out)


def _grab_with_pil(out: Path) -> None:
    try:
        from PIL import Image, ImageGrab
    except ImportError as exc:
        raise ClipboardError("读取剪贴板需要 Pillow：pip install Pillow") from exc

    img = ImageGrab.grabclipboard()
    if img is None:
        raise ClipboardError("剪贴板中没有图片。")

    # Windows：从资源管理器复制文件时，PIL 返回文件路径列表
    if isinstance(img, list):
        if not img:
            raise ClipboardError("剪贴板中没有图片。")
        Image.open(img[0]).save(out, "PNG")
        return

    img.save(out, "PNG")


def _grab_macos_pngpaste(out: Path) -> None:
    try:
        result = subprocess.run(
            ["pngpaste", str(out)], capture_output=True, timeout=10
        )
    except FileNotFoundError:
        raise ClipboardError(
            "剪贴板中没有图片。macOS 需要 pngpaste 兜底：brew install pngpaste"
        )
    if result.returncode != 0:
        raise ClipboardError("剪贴板中没有图片（pngpaste 失败）。")


def _grab_linux(out: Path) -> None:
    attempts = [
        (["wl-paste", "--type", "image/png"], "wl-clipboard"),
        (["xclip", "-selection", "clipboard", "-t", "image/png", "-o"], "xclip"),
    ]
    errors: list[str] = []
    for cmd, pkg in attempts:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
        except FileNotFoundError:
            errors.append(f"未安装 {pkg}")
            continue
        if result.returncode == 0 and result.stdout:
            out.write_bytes(result.stdout)
            return
        errors.append(f"{pkg} 返回空图片")
    raise ClipboardError(
        "剪贴板中没有图片。请安装 wl-clipboard（Wayland）或 xclip（X11）。"
        f"尝试结果：{', '.join(errors)}"
    )
