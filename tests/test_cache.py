"""会话结果缓存测试。"""

from deepseek_vision_mcp.cache import ResultCache, make_cache_key


def test_cache_key_changes_with_prompt_or_model():
    base = make_cache_key(["image"], "describe", "https://api", ["model-a"])
    assert base != make_cache_key(["image"], "ocr", "https://api", ["model-a"])
    assert base != make_cache_key(["image"], "describe", "https://api", ["model-b"])


def test_lru_evicts_oldest_entry():
    cache = ResultCache(max_entries=2, ttl_seconds=60)
    cache.set("a", {"text": "A"})
    cache.set("b", {"text": "B"})
    assert cache.get("a")["text"] == "A"
    cache.set("c", {"text": "C"})
    assert cache.get("b") is None
    assert cache.get("a")["text"] == "A"
