"""deepseek-vision-mcp 可复现对比测试。

用法（在仓库根目录）：
    python scripts/benchmark.py install            # 从零安装耗时（全新 venv + pip install 正式包）
    python scripts/benchmark.py ocr --image X      # OCR 准确性（需 API Key）
    python scripts/benchmark.py repeat --image X   # 同图重复调用延迟：缓存 vs 未缓存（需 API Key）
    python scripts/benchmark.py rate-limit --n 5   # 连续请求后 429 恢复表现（需 API Key，会消耗免费额度）
    python scripts/benchmark.py key-leak --key K   # Key 是否进入配置/日志/模型上下文（无需 API Key）

环境变量：VISION_API_KEY 等（与 MCP Server 共用配置）。
结果输出 JSON 便于记录；完整测试步骤见 docs/BENCHMARK.md。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _print_result(name: str, payload: dict) -> None:
    print(json.dumps({"benchmark": name, **payload}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# install：从零安装耗时
# ---------------------------------------------------------------------------
def bench_install(python: str) -> int:
    start = time.time()
    with tempfile.TemporaryDirectory(prefix="dvm-bench-install-") as tmp:
        venv = Path(tmp) / "venv"
        subprocess.run([python, "-m", "venv", str(venv)], check=True)
        pip = venv / "bin" / "pip"
        install_start = time.time()
        subprocess.run(
            [str(pip), "install", "--quiet", "deepseek-vision-mcp"],
            check=True, capture_output=True,
        )
        install_secs = round(time.time() - install_start, 2)
        out = subprocess.run(
            [str(venv / "bin" / "python"), "-c",
             "import deepseek_vision_mcp, importlib.metadata as m; "
             "print(m.version('deepseek-vision-mcp'))"],
            capture_output=True, text=True,
        ).stdout.strip()
    total_secs = round(time.time() - start, 2)
    _print_result("install", {
        "python": python,
        "installed_version": out or "?",
        "pip_install_secs": install_secs,
        "total_secs": total_secs,
        "note": "从创建 venv 到 pip install 正式包（PyPI）完成",
    })
    return 0


# ---------------------------------------------------------------------------
# ocr：OCR 准确性（对参考图执行 ocr task，统计期望子串命中）
# ---------------------------------------------------------------------------
def bench_ocr(image: str, expected: list[str]) -> int:
    from deepseek_vision_mcp.config import load_config
    from deepseek_vision_mcp.image_utils import load_image_as_base64
    from deepseek_vision_mcp.prompts import TASK_PROMPTS
    from deepseek_vision_mcp.providers import build_provider

    cfg = load_config()
    data_uri, mime = load_image_as_base64(
        image, max_size_kb=cfg.max_image_size_kb,
        download_timeout=cfg.download_timeout_seconds,
        allowed_formats=cfg.allowed_formats,
        allow_private=cfg.allow_private_urls,
    )
    provider = build_provider(cfg)
    start = time.time()
    try:
        outcome = provider.analyze(data_uri, TASK_PROMPTS["ocr"])
    finally:
        provider.close()
    elapsed = round(time.time() - start, 2)
    text = outcome["text"]
    hits = {w: (w.lower() in text.lower()) for w in expected}
    _print_result("ocr", {
        "image": image,
        "elapsed_secs": elapsed,
        "model": outcome.get("model"),
        "expected_substrings": expected,
        "hits": hits,
        "hit_rate": round(sum(hits.values()) / max(1, len(hits)), 2),
        "output_head": text[:120],
    })
    return 0


# ---------------------------------------------------------------------------
# repeat：同图重复调用延迟（第一次未缓存 vs 第二次缓存）
# ---------------------------------------------------------------------------
def bench_repeat(image: str, prompt: str) -> int:
    from deepseek_vision_mcp.config import load_config
    from deepseek_vision_mcp.server import create_server

    cfg = load_config()
    mcp = create_server(config=cfg)
    fn = mcp._tool_manager._tools["analyze_image"].fn
    timings = []
    for i in range(2):
        start = time.time()
        raw = fn(image, prompt)
        elapsed = round(time.time() - start, 3)
        payload = json.loads(raw)
        timings.append({"round": i + 1, "elapsed_secs": elapsed,
                        "cached": payload.get("cached", False),
                        "success": payload.get("success")})
        time.sleep(0.5)
    first = timings[0]["elapsed_secs"]
    second = timings[1]["elapsed_secs"]
    _print_result("repeat", {
        "image": image,
        "prompt": prompt,
        "rounds": timings,
        "uncached_secs": first,
        "cached_secs": second,
        "speedup_if_cached": round(first / second, 2) if second > 0 and timings[1]["cached"] else None,
    })
    return 0


# ---------------------------------------------------------------------------
# rate-limit：连续请求后 429 的恢复表现
# ---------------------------------------------------------------------------
def bench_rate_limit(n: int, image: str) -> int:
    from deepseek_vision_mcp.config import load_config
    from deepseek_vision_mcp.server import create_server

    cfg = load_config()
    mcp = create_server(config=cfg)
    fn = mcp._tool_manager._tools["analyze_image"].fn
    rounds = []
    saw_429 = False
    for i in range(n):
        start = time.time()
        raw = fn(image, "请描述这张图片")
        elapsed = round(time.time() - start, 3)
        payload = json.loads(raw)
        is_429 = "429" in payload.get("result", "") or "1305" in payload.get("result", "")
        saw_429 = saw_429 or is_429
        rounds.append({
            "round": i + 1, "success": payload.get("success"),
            "rate_limited": is_429, "elapsed_secs": elapsed,
            "attempts": payload.get("attempts", 0),
        })
        time.sleep(1)
    recovered = saw_429 and any(r["success"] for r in rounds[rounds.index(next(
        (r for r in rounds if r["rate_limited"]), {"round": n})):])
    _print_result("rate-limit", {
        "n_requests": n, "rounds": rounds,
        "saw_429": saw_429, "recovered_after_429": recovered,
        "note": "免费模型 429 属正常；关注是否自动重试成功（attempts>1 且 success）",
    })
    return 0


# ---------------------------------------------------------------------------
# key-leak：Key 是否进入配置/日志/模型上下文
# ---------------------------------------------------------------------------
def bench_key_leak(test_key: str) -> int:
    checks: dict[str, bool] = {}
    # 1) 仓库文件不应包含该 Key
    repo_hits = []
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
            continue
        if any(x in p.parts for x in ("node_modules", ".pytest_cache", ".tools",
                                      ".runtime-dist", "egg-info", "build", "dist")):
            continue
        try:
            if p.suffix in (".py", ".md", ".toml", ".json", ".yml", ".yaml",
                            ".example", ".txt", ".js", ".mjs", ".sh", ".ps1"):
                if test_key in p.read_text(encoding="utf-8", errors="ignore"):
                    repo_hits.append(str(p))
        except OSError:
            pass
    checks["repo_does_not_contain_key"] = not repo_hits

    # 2) vision_status 输出不应包含 Key
    import os as _os

    from deepseek_vision_mcp.config import load_config
    from deepseek_vision_mcp.server import create_server
    _os.environ.setdefault("VISION_API_KEY", test_key)
    cfg = load_config()
    mcp = create_server(config=cfg)
    status = mcp._tool_manager._tools["vision_status"].fn()
    checks["vision_status_masks_key"] = test_key not in status

    # 3) 配置加载不把 Key 写回配置文件
    checks["config_files_not_rewritten"] = not any(
        p.exists() and test_key in p.read_text(encoding="utf-8", errors="ignore")
        for p in (REPO_ROOT / ".env", REPO_ROOT / "config.json")
    )

    # 4) 运行一次工具（无真实 Key 时返回错误），stderr 日志不应含 Key
    import io as _io
    import logging
    buf = _io.StringIO()
    handler = logging.StreamHandler(buf)
    logging.getLogger("deepseek_vision_mcp").addHandler(handler)
    fn = mcp._tool_manager._tools["analyze_image"].fn
    try:
        fn("examples/test_image.jpg")
    except Exception:
        pass
    logs = buf.getvalue()
    checks["logs_do_not_contain_key"] = test_key not in logs

    _print_result("key-leak", {
        "test_key_masked": test_key[:8] + "****",
        "checks": checks,
        "repo_hits": [str(p) for p in repo_hits[:5]],
        "all_pass": all(checks.values()),
    })
    return 0 if all(checks.values()) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("install", help="从零安装耗时")
    p.add_argument("--python", default=sys.executable)

    p = sub.add_parser("ocr", help="OCR 准确性")
    p.add_argument("--image", default=str(REPO_ROOT / "examples" / "test_image.jpg"))
    p.add_argument("--expected", nargs="*",
                   default=["DeepSeek", "Vision", "MCP", "Hello", "images"])

    p = sub.add_parser("repeat", help="同图重复调用延迟")
    p.add_argument("--image", default=str(REPO_ROOT / "examples" / "test_image.jpg"))
    p.add_argument("--prompt", default="请描述这张图片")

    p = sub.add_parser("rate-limit", help="连续 429 恢复表现")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--image", default=str(REPO_ROOT / "examples" / "test_image.jpg"))

    p = sub.add_parser("key-leak", help="Key 泄漏检查")
    p.add_argument("--key", default=None,
                   help="测试用假 Key；不传时随机生成（保证不在仓库中出现）")

    args = parser.parse_args(argv)
    if args.cmd == "install":
        return bench_install(args.python)
    if args.cmd == "ocr":
        return bench_ocr(args.image, args.expected)
    if args.cmd == "repeat":
        return bench_repeat(args.image, args.prompt)
    if args.cmd == "rate-limit":
        return bench_rate_limit(args.n, args.image)
    if args.cmd == "key-leak":
        import uuid
        test_key = args.key or f"sk-leaktest-{uuid.uuid4().hex[:16]}"
        return bench_key_leak(test_key)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
