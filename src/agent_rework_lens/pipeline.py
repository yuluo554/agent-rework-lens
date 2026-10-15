"""编排层（🟢）：CLI 只做"解析参数 → 调 pipeline → 格式化输出"。

把全链路行为上收成公开函数组，测试与未来交付形态（如报告章节）都消费同一处实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import config
from .discovery import DiscoveryResult, discover_sources
from .errors import NoSourcesFound, StageNotReady
from .parsers import parse_claude_session, parse_codex_session


@dataclass(frozen=True)
class SourcesOutcome:
    discovery: DiscoveryResult

    @property
    def found_any(self) -> bool:
        return len(self.discovery.locations) > 0


def run_sources(
    claude_home: Optional[str] = None,
    codex_home: Optional[str] = None,
    source_filter: str = "auto",
) -> SourcesOutcome:
    return SourcesOutcome(discovery=discover_sources(claude_home, codex_home, source_filter))


def run_scan(
    claude_home: Optional[str] = None,
    codex_home: Optional[str] = None,
    source_filter: str = "auto",
):
    """全链路 scan：发现 → 解析 → 引擎 → 报告。

    骨架期（M0）：发现可用；解析层于 M1 数据核对、M2 实现后启用——在此之前以
    ``StageNotReady``（退出码 4）明确拦截，**不产出假报告**（K7）。
    """
    discovery = discover_sources(claude_home, codex_home, source_filter)
    if not discovery.locations:
        raise NoSourcesFound(describe_missing(discovery))

    # 触发对应源解析器的护栏，使"未就绪"提示尽量具体（M2 起由真实解析接管）
    for loc in discovery.locations:
        if loc.kind == "claude_sessions" and loc.files:
            parse_claude_session(loc.files[0])
        elif loc.kind == "codex_sessions" and loc.files:
            parse_codex_session(loc.files[0])

    raise StageNotReady("scan 全链路（解析→引擎→报告）", "M2–M4 逐段启用")


def describe_missing(discovery: DiscoveryResult) -> str:
    parts = ["%s（查过：%s）" % (m.kind, " | ".join(m.looked_at)) for m in discovery.missing]
    looked = "；".join(parts) if parts else "（无记录）"
    return (
        "未发现可分析日志源。已检查：%s。提示：可用 --claude-home/--codex-home "
        "或环境变量 %s/%s 指定日志位置。"
        % (looked, config.ENV_CLAUDE_HOME, config.ENV_CODEX_HOME)
    )
