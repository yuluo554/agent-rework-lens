"""编排层（🟢）：CLI 只做"解析参数 → 调 pipeline → 格式化输出"。

把全链路行为上收成公开函数组，测试与未来交付形态（如报告章节）都消费同一处实现。

M2 起 ``run_scan`` 完成"发现 → 解析 → 统一 IR"并输出确定性摘要；引擎（M3）与
报告（M4/M5）接入前，摘要**只含会话/事件/注记计数**，不含判定结论（K6/K7）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import config
from .discovery import (
    KIND_CLAUDE_FILE_HISTORY,
    KIND_CLAUDE_SESSIONS,
    KIND_CODEX_SESSIONS,
    DiscoveryResult,
    discover_sources,
)
from .errors import NoSourcesFound
from .ir import KIND_EDIT, KIND_MULTIEDIT, KIND_WRITE, SessionIR
from .parsers import parse_claude_session, parse_codex_session
from .parsers.claude_code import read_version_chains


@dataclass(frozen=True)
class SourcesOutcome:
    discovery: DiscoveryResult

    @property
    def found_any(self) -> bool:
        return len(self.discovery.locations) > 0


@dataclass(frozen=True)
class ParsedSession:
    """一个会话文件的解析结果（IR + 会话绑定的版本链）。"""

    ir: SessionIR
    # Claude 专属：file-history 实读版本链 {hash_stem: {"versions", "files", "max_version"}}；
    # Codex 无此源（R5：返工判据以 apply_patch 计数为主）→ 空 dict
    version_chains: Dict[str, dict]

    @property
    def session_id(self) -> str:
        return self.ir.meta.session_id

    @property
    def write_event_count(self) -> int:
        return sum(
            1 for e in self.ir.tool_events if e.kind in (KIND_EDIT, KIND_MULTIEDIT, KIND_WRITE)
        )


@dataclass(frozen=True)
class ScanOutcome:
    """scan 第一阶段（M2）：发现 → 解析 → IR 摘要（零判定零外链零时钟，K6）。"""

    discovery: DiscoveryResult
    sessions: Tuple[ParsedSession, ...]
    # {session_id: {hash_stem: chain}}（仅 Claude 源有绑定）
    version_chains: Dict[str, Dict[str, dict]]

    @property
    def tool_event_count(self) -> int:
        return sum(len(s.ir.tool_events) for s in self.sessions)

    @property
    def token_event_count(self) -> int:
        return sum(len(s.ir.token_events) for s in self.sessions)

    @property
    def note_count(self) -> int:
        return sum(len(s.ir.notes) for s in self.sessions)


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
) -> ScanOutcome:
    """全链路 scan 第一阶段：发现 → 解析 → 统一 IR（确定性输出）。

    M2 语义：解析层已启用（K2：退出码 4 的"解析层"项退役）；引擎与报告于 M3/M4
    接入——摘要只含计数，不含任何返工/重复判定。
    """
    discovery = discover_sources(claude_home, codex_home, source_filter)
    if not discovery.locations:
        raise NoSourcesFound(describe_missing(discovery))

    history_root = None
    claude_sessions_loc = _find_location(discovery, KIND_CLAUDE_SESSIONS)
    history_loc = _find_location(discovery, KIND_CLAUDE_FILE_HISTORY)
    if history_loc is not None:
        history_root = Path(history_loc.root)
    elif claude_sessions_loc is not None:
        # sessions 目录来自某个 claude_home；file-history 未命中时按同一 home 实读（缺失 → 空链）
        history_root = Path(claude_sessions_loc.root).parent.parent / "file-history"

    # file-history 实读一次（K4：只实读目录，不反推；目录缺失 → 空链，missing 已披露）
    claude_chains = read_version_chains(history_root) if history_root is not None else {}

    sessions: List[ParsedSession] = []
    chains_by_session: Dict[str, Dict[str, dict]] = {}

    if claude_sessions_loc is not None:
        for file_path in claude_sessions_loc.files:
            ir = parse_claude_session(file_path)
            sessions.append(
                ParsedSession(ir=ir, version_chains=claude_chains.get(ir.meta.session_id, {}))
            )
            if ir.meta.session_id in claude_chains:
                chains_by_session[ir.meta.session_id] = claude_chains[ir.meta.session_id]

    codex_loc = _find_location(discovery, KIND_CODEX_SESSIONS)
    if codex_loc is not None:
        for file_path in codex_loc.files:
            ir = parse_codex_session(file_path)
            sessions.append(ParsedSession(ir=ir, version_chains={}))

    # 确定性输出：按 (source, session_id, source_file) 排序
    sessions.sort(key=lambda s: (s.ir.meta.source, s.ir.meta.session_id, s.ir.meta.source_file))
    return ScanOutcome(
        discovery=discovery,
        sessions=tuple(sessions),
        version_chains=chains_by_session,
    )


def _find_location(discovery: DiscoveryResult, kind: str):
    for loc in discovery.locations:
        if loc.kind == kind:
            return loc
    return None


def describe_missing(discovery: DiscoveryResult) -> str:
    parts = ["%s（查过：%s）" % (m.kind, " | ".join(m.looked_at)) for m in discovery.missing]
    looked = "；".join(parts) if parts else "（无记录）"
    return (
        "未发现可分析日志源。已检查：%s。提示：可用 --claude-home/--codex-home "
        "或环境变量 %s/%s 指定日志位置。"
        % (looked, config.ENV_CLAUDE_HOME, config.ENV_CODEX_HOME)
    )
