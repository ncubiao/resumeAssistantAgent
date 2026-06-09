"""手动测试 LLM 连通性 / 简历解析的 CLI。

使用方式：
    # 查看配置与依赖状态
    python -m scripts.test_llm info

    # 发起一次简单的 LLM 调用
    python -m scripts.test_llm ping

    # 解析 sample 简历
    python -m scripts.test_llm parse data/samples/sample_resume_zhangsan.txt

    # 传入自定义文本
    python -m scripts.test_llm parse-text "张三，python 后端，5 年经验..."
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 把 backend 目录加入 sys.path 以 import app.*
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# 现在 import backend 侧模块
from app.agents.nodes.parser_agent import run as run_parser  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.utils.llm_client import llm_client  # noqa: E402


def _print_title(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def cmd_info() -> int:
    _print_title("LLM 配置信息")
    print(f" provider     : {llm_client.provider}")
    print(f" model        : {llm_client.model}")
    print(f" base_url     : {llm_client.base_url}")
    print(f" api_key_len  : {len(llm_client.api_key or '')}")
    print(f" available    : {llm_client.available}")
    print(f" log_level    : {settings.log_level}")
    print()
    print(" 提示: 如果 api_key_len=0，说明未配置 LLM_API_KEY / key 中含 '你的' 字样。")
    print("       可用时 resume 解析走 LLM，否则走启发式 fallback。")
    return 0


def cmd_ping() -> int:
    _print_title("LLM Ping Test")
    reply = llm_client.invoke("你好，请用一句话介绍你自己。")
    if not reply:
        print(" ❌ LLM 未返回响应 (可能未配置 key 或依赖缺失)。走启发式 fallback。")
        return 1
    print(f" ✅ LLM 响应 OK (provider={llm_client.provider})")
    print(f" 回复: {reply[:200]}")
    return 0


def cmd_parse(path: str) -> int:
    p = Path(path)
    if not p.exists():
        print(f"文件不存在: {p}")
        return 2
    text = p.read_text(encoding="utf-8", errors="ignore")
    _print_title(f"解析 {p.name} (len={len(text)})")
    result = run_parser(text)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
    return 0


def cmd_parse_text(text: str) -> int:
    _print_title(f"解析文本 (len={len(text)})")
    result = run_parser(text)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "info":
        return cmd_info()
    if cmd == "ping":
        return cmd_ping()
    if cmd == "parse" and len(argv) >= 3:
        return cmd_parse(argv[2])
    if cmd == "parse-text" and len(argv) >= 3:
        return cmd_parse_text(" ".join(argv[2:]))
    print(f"未知命令: {cmd}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
