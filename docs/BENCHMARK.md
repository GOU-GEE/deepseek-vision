# 可复现对比测试（Benchmark）

针对「给 DeepSeek 纯文本模型加视觉」的 6 个关键指标提供**可复现**的测试
脚本与记录模板。脚本：`scripts/benchmark.py`。

## 环境

- 机器：macOS / Linux（Windows 路径把 `venv/bin` 换成 `venv\Scripts`）
- Python 3.10+（测试机可用任意版本，脚本会如实记录）
- 需 API Key 的子命令：`ocr` / `repeat` / `rate-limit`（用 `VISION_API_KEY`
  等环境变量，与 MCP Server 共用配置）
- 无需 API Key 的子命令：`install` / `key-leak`

## 测试项与命令

| 指标 | 命令 | 说明 | 需要 Key |
| --- | --- | --- | --- |
| 从零安装时间 | `python scripts/benchmark.py install [--python PATH]` | 全新 venv + `pip install deepseek-vision-mcp`（PyPI 正式包）耗时 | 否 |
| OCR 准确性 | `python scripts/benchmark.py ocr --image X [--expected 词1 词2 ...]` | 对参考图执行 `ocr` 任务，统计期望子串命中率 | 是 |
| 同图重复调用延迟 | `python scripts/benchmark.py repeat --image X --prompt P` | 同一张图同一 prompt 连调两次，对比未缓存/缓存延迟与 `cached` 标志 | 是 |
| 连续 429 恢复表现 | `python scripts/benchmark.py rate-limit --n 5 --image X` | 连续 N 次请求，观察是否出现 429、以及后续是否自动重试成功（`attempts>1`） | 是 |
| Key 泄漏检查 | `python scripts/benchmark.py key-leak [--key K]` | 随机测试 Key：仓库文件 / vision_status 输出 / 配置文件 / 运行日志 四处均不得出现 | 否 |

## 复现步骤（完整一轮）

```bash
cd /Users/goulijun/Documents/project/DeepSeek-vision-mcp

# 0) 前置：测试 Key 只放环境变量，不写进任何文件
export VISION_API_KEY=你的Key
export VISION_MODEL=glm-4.6v-flash
export VISION_BASE_URL=https://open.bigmodel.cn/api/paas/v4

# 1) 从零安装时间（无需 Key）
python3 scripts/benchmark.py install

# 2) OCR 准确性（需 Key；examples/test_image.jpg 含 "DeepSeek Vision MCP" 等文字）
python3 scripts/benchmark.py ocr --image examples/test_image.jpg

# 3) 同图重复调用延迟（需 Key）
python3 scripts/benchmark.py repeat --image examples/test_image.jpg

# 4) 连续 429 恢复表现（需 Key，会消耗免费额度，建议挑非高峰）
python3 scripts/benchmark.py rate-limit --n 5

# 5) Key 泄漏检查（无需 Key）
python3 scripts/benchmark.py key-leak
```

> 429 依赖免费模型的实时限流状态，同一次运行内不一定触发；
> 判定标准是「触发 429 后能自动重试成功」，见输出中的 `attempts` 与 `success`。

## 结果记录模板

把每次运行的关键输出填入下表，标注机器/时间/模型，便于横向对比：

| 指标 | 本次结果 | 机器/日期/模型 |
| --- | --- | --- |
| 从零安装（venv+pip） | `0.3.2` / 约 30 s | macOS M2 / 2026-08-15 / — |
| OCR 命中率 | e.g. 100%（4/4 词命中） | … / glm-4.6v-flash |
| 同图首次延迟 / 二次延迟 | e.g. 2.1 s / 0.02 s（cached=true） | … / glm-4.6v-flash |
| 429 触发次数 / 恢复 | e.g. 2 次 429，均自动重试成功 | … / glm-4.6v-flash |
| Key 泄漏检查 | 全部通过（repo/status/config/log） | — / — |

## 对比口径说明

- 「从零安装」指**官方发布物**（PyPI `deepseek-vision-mcp`），不是源码
  editable 安装；若对比其他插件，用其对应的官方安装方式（如
  `dsh plugin --profile web add <pkg>`）单独计时。
- OCR 准确性的参考图与期望词可自定义（`--image` / `--expected`），
  换图时在结果模板中注明，保证可比。
- 缓存命中判定以工具返回的 `cached` 字段为准（LRU + TTL，默认 128 条 / 1h）。
