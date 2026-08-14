"""轻量会话缓存：避免同一 MCP 进程重复分析相同图片。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Iterable, Optional


def make_cache_key(
    image_data_uris: Iterable[str], prompt: str, base_url: str, models: Iterable[str]
) -> str:
    """对实际图片内容、提示词和后端配置生成稳定哈希，不保存图片本身。"""
    digest = hashlib.sha256()
    for value in image_data_uris:
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    digest.update(prompt.encode("utf-8"))
    digest.update(b"\0")
    digest.update(base_url.encode("utf-8"))
    digest.update(b"\0")
    digest.update(json.dumps(list(models), ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


class ResultCache:
    """线程安全的 TTL + LRU 内存缓存；进程退出即清空。"""

    def __init__(self, max_entries: int = 128, ttl_seconds: int = 3600) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            created_at, value = item
            if now - created_at > self.ttl_seconds:
                del self._items[key]
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return dict(value)

    def set(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), dict(value))
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {"entries": len(self._items), "hits": self.hits, "misses": self.misses}
