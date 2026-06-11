"""轻量进程内指标采集（无第三方依赖，Prometheus 文本格式暴露）。

为什么不用 prometheus_client：作品集单进程场景，手写一个零依赖的计数器 +
文本渲染足够，且能讲清"指标基数控制 / 暴露格式"的设计点。多实例 / 生产可平滑
换成 prometheus_client + 多进程模式。

采集项：
- http_requests_total{method,path,status}
- http_request_duration_seconds_sum / _count{method,path}（可算平均延迟）
- llm_calls_total / llm_errors_total
路径基数控制：UUID 与长数字段被归一化为 {id}，避免标签爆炸。
"""
from __future__ import annotations

import re
from collections import defaultdict
from threading import Lock

_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_NUM_RE = re.compile(r"/\d+(?=/|$)")


def normalize_path(path: str) -> str:
    """把路径中的 UUID / 数字 ID 归一化为 {id}，控制指标基数。"""
    p = _UUID_RE.sub("{id}", path)
    p = _NUM_RE.sub("/{id}", p)
    return p


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
        self.duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self.llm_calls_total: int = 0
        self.llm_errors_total: int = 0

    def observe_request(self, method: str, path: str, status: int, duration_s: float) -> None:
        path = normalize_path(path)
        with self._lock:
            self.requests_total[(method, path, status)] += 1
            self.duration_sum[(method, path)] += duration_s
            self.duration_count[(method, path)] += 1

    def inc_llm(self, error: bool = False) -> None:
        with self._lock:
            self.llm_calls_total += 1
            if error:
                self.llm_errors_total += 1

    def reset(self) -> None:
        with self._lock:
            self.requests_total.clear()
            self.duration_sum.clear()
            self.duration_count.clear()
            self.llm_calls_total = 0
            self.llm_errors_total = 0

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            lines.append("# HELP http_requests_total Total HTTP requests.")
            lines.append("# TYPE http_requests_total counter")
            for (method, path, status), count in sorted(self.requests_total.items()):
                lines.append(
                    f'http_requests_total{{method="{_esc(method)}",path="{_esc(path)}",status="{status}"}} {count}'
                )

            lines.append("# HELP http_request_duration_seconds Request duration sum/count.")
            lines.append("# TYPE http_request_duration_seconds summary")
            for (method, path), total in sorted(self.duration_sum.items()):
                cnt = self.duration_count[(method, path)]
                lbl = f'method="{_esc(method)}",path="{_esc(path)}"'
                lines.append(f"http_request_duration_seconds_sum{{{lbl}}} {total:.6f}")
                lines.append(f"http_request_duration_seconds_count{{{lbl}}} {cnt}")

            lines.append("# HELP llm_calls_total Total LLM invocations.")
            lines.append("# TYPE llm_calls_total counter")
            lines.append(f"llm_calls_total {self.llm_calls_total}")
            lines.append("# HELP llm_errors_total Failed LLM invocations.")
            lines.append("# TYPE llm_errors_total counter")
            lines.append(f"llm_errors_total {self.llm_errors_total}")
        return "\n".join(lines) + "\n"


# 全局单例
metrics = Metrics()

__all__ = ["Metrics", "metrics", "normalize_path"]
