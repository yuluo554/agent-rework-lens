"""编排层（🟢）：CLI 只做"解析参数 → 调 pipeline → 格式化输出"。

把全链路行为上收成公开函数组，测试与未来交付形态（如报告章节）都消费同一处实现。

M2 起 ``run_scan`` 完成"发现 → 解析 → 统一 IR"并输出确定性摘要；引擎（M3）与
报告（M4/M5）接入前，摘要**只含会话/事件/注记计数**，不含判定结论（K6/K7）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from . import config
from . import __version__
from .discovery import (
    KIND_CLAUDE_FILE_HISTORY,
    KIND_CLAUDE_SESSIONS,
    KIND_CODEX_SESSIONS,
    DiscoveryResult,
    discover_sources,
)
from .engine.metrics import (
    DUP_DISCLOSURE,
    SessionMetrics,
    compute_session_metrics,
    find_dup_candidates,
    symbols_from_write_payloads,
)
from .engine.rework import VERDICT_REWORK, ReworkFinding, analyze_rework
from .engine.symbols import Symbol, extract_defined_symbols
from .errors import NoSourcesFound
from .ir import KIND_EDIT, KIND_MULTIEDIT, KIND_READ, KIND_WRITE, SessionIR
from .parsers import parse_claude_session, parse_codex_session
from .parsers.claude_code import read_snapshot_file_map, read_version_chains
from .report.model import ReportMeta, ReportModel


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
    """scan 全链路（M3）：发现 → 解析 → IR → 引擎判定。

    ``findings`` 汇总各会话的返工判定（附 ``session_id`` 溯源）；报告层（M5）
    在此之上组装 ReportModel 并渲染。摘要文本输出仍带解析注记（K7 显式可见）。
    """

    discovery: DiscoveryResult
    sessions: Tuple[ParsedSession, ...]
    # {session_id: {hash_stem: chain}}（仅 Claude 源有绑定）
    version_chains: Dict[str, Dict[str, dict]]
    findings: Tuple[ReworkFinding, ...] = ()
    # 会话级指标（M5 报告层组装用；与 sessions 同序）
    session_metrics: Tuple[SessionMetrics, ...] = ()
    # 报告注记（披露制文本 + 未支持语言/未取到已有符号等显式说明）
    report_notes: Tuple[str, ...] = ()

    @property
    def tool_event_count(self) -> int:
        return sum(len(s.ir.tool_events) for s in self.sessions)

    @property
    def token_event_count(self) -> int:
        return sum(len(s.ir.token_events) for s in self.sessions)

    @property
    def note_count(self) -> int:
        return sum(len(s.ir.notes) for s in self.sessions)

    @property
    def rework_count(self) -> int:
        return sum(1 for f in self.findings if f.verdict == VERDICT_REWORK)


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
    """全链路 scan：发现 → 解析 → 统一 IR → 引擎返工判定（确定性输出）。

    M3 语义：引擎已接入（verdict 三态 + reasons + 证据锚点）；报告渲染于 M4/M5。
    判定阈值取 config 单点（K1）；版本链只实读不反推（K4）。
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
    findings: List[ReworkFinding] = []
    metrics_list: List[SessionMetrics] = []
    report_notes: List[str] = []

    if claude_sessions_loc is not None:
        for file_path in claude_sessions_loc.files:
            ir = parse_claude_session(file_path)
            session_chains = claude_chains.get(ir.meta.session_id, {})
            snap_map = read_snapshot_file_map(file_path)
            sessions.append(ParsedSession(ir=ir, version_chains=session_chains))
            if ir.meta.session_id in claude_chains:
                chains_by_session[ir.meta.session_id] = claude_chains[ir.meta.session_id]
            findings.extend(analyze_rework(ir, session_chains, snap_map))
            metrics, notes = _session_metrics_from_file(ir, Path(file_path), source_root=Path(claude_sessions_loc.root))
            metrics_list.append(metrics)
            report_notes.extend(notes)

    codex_loc = _find_location(discovery, KIND_CODEX_SESSIONS)
    if codex_loc is not None:
        for file_path in codex_loc.files:
            ir = parse_codex_session(file_path)
            sessions.append(ParsedSession(ir=ir, version_chains={}))
            findings.extend(analyze_rework(ir, {}, {}))
            metrics, notes = _session_metrics_from_file(ir, Path(file_path), source_root=None)
            metrics_list.append(metrics)
            report_notes.extend(notes)

    # 确定性输出：按 (source, session_id, source_file) 排序（指标与会话同键同步）
    order = sorted(
        range(len(sessions)),
        key=lambda i: (sessions[i].ir.meta.source, sessions[i].ir.meta.session_id, sessions[i].ir.meta.source_file),
    )
    sessions = [sessions[i] for i in order]
    metrics_list = [metrics_list[i] for i in order]
    findings.sort(key=lambda f: (f.session_id, f.file_path, f.verdict))
    return ScanOutcome(
        discovery=discovery,
        sessions=tuple(sessions),
        version_chains=chains_by_session,
        findings=tuple(findings),
        session_metrics=tuple(metrics_list),
        report_notes=tuple(report_notes),
    )


def _session_metrics_from_file(
    ir: SessionIR, session_path: Path, source_root: Optional[Path]
) -> Tuple[SessionMetrics, Tuple[str, ...]]:
    """单会话指标 + 符号候选（M5 报告层组装；确定性，K11）。

    新写符号：从会话文件**重读 Write 载荷**提取（IR 不携带载荷，与 bench 同一做法）；
    语言按写入文件扩展名判定，不支持 → 显式披露（不猜测，K7 同族）。
    已有符号：Read 事件指向且磁盘存在的 .py 文件提取；读不到 → 显式披露。
    ``source_root`` 为 None（Codex 源）→ 不做符号候选（R5：apply_patch 载荷形态
    与 Claude Write 不同，不编造字段——披露制说明）。
    """
    notes: List[str] = []
    write_payloads: List[Tuple[str, str]] = []
    read_targets: List[str] = []
    for event in ir.tool_events:
        if event.kind == KIND_READ and event.file_path:
            read_targets.append(event.file_path)
    if source_root is not None:
        for path_str, content, language in _iter_write_payloads(session_path, ir):
            if language is None:
                notes.append(
                    "会话 %s：Write 载荷 %s 非首期支持语言（%s），符号提取显式跳过（不猜测）"
                    % (ir.meta.session_id, path_str, config.SUPPORTED_SYMBOL_LANGUAGES)
                )
                continue
            write_payloads.append((language, content))
        existing = _existing_symbols(read_targets, source_root, ir, notes)
    else:
        existing = ()
        if any(e.kind in (KIND_EDIT, KIND_WRITE, KIND_MULTIEDIT) for e in ir.tool_events):
            notes.append(
                "会话 %s（%s 源）：符号候选未启用（apply_patch 载荷无独立 file_path+content "
                "双字段形态，不编造——R5/D-M1-4 口径）" % (ir.meta.session_id, ir.meta.source)
            )
    new_syms = symbols_from_write_payloads(write_payloads)
    candidates = find_dup_candidates(new_syms, existing) if new_syms and existing else ()
    if candidates:
        notes.append("会话 %s：%s" % (ir.meta.session_id, DUP_DISCLOSURE))
    evidence = _session_evidence(ir, session_path)
    metrics = compute_session_metrics(
        ir.meta.session_id,
        ir.tool_events,
        write_payloads=write_payloads,
        existing_symbols=existing,
        new_evidence=evidence,
        existing_evidence=evidence,
    )
    return metrics, tuple(notes)


def _session_evidence(ir: SessionIR, session_path: Path) -> str:
    """会话级证据锚点：``源文件:会话 id``（报告候选节可溯源）。"""
    return "%s:%s" % (ir.meta.source_file or session_path.name, ir.meta.session_id)


def _iter_write_payloads(session_path: Path, ir: SessionIR) -> Iterator[Tuple[str, str, Optional[str]]]:
    """重读会话文件的 Write 载荷，按源文件出现顺序输出 ``(路径, 内容, language)``。

    与 bench ``_write_payloads`` 同一重读策略；扩展名 → language 映射在 config 单点，
    不在支持集 → language=None（上游显式披露，不猜测，K7 同族）。
    """
    for line in session_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant":
            continue
        for block in (obj.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Write":
                continue
            input_obj = block.get("input") or {}
            content = input_obj.get("content")
            path_str = input_obj.get("file_path")
            if not isinstance(content, str):
                continue
            language = _language_for_path(path_str if isinstance(path_str, str) else "")
            yield (path_str if isinstance(path_str, str) else "", content, language)


def _language_for_path(path_str: str) -> Optional[str]:
    suffix = Path(path_str).suffix.lower()
    return config.SYMBOL_LANGUAGE_BY_SUFFIX.get(suffix)


def _existing_symbols(
    read_targets: List[str], source_root: Path, ir: SessionIR, notes: List[str]
) -> Tuple[Symbol, ...]:
    """Read 过且磁盘存在的 .py 文件 → 已有符号清单（04 §7.3：read 事件 + 路径存在性）。"""
    collected: List[Symbol] = []
    seen: set = set()
    for target in sorted(set(read_targets)):
        path = _resolve_existing(target, source_root)
        if path is None:
            notes.append(
                "会话 %s：Read 目标 %s 磁盘不存在或不在源根内，已有符号提取跳过（显式披露）"
                % (ir.meta.session_id, target)
            )
            continue
        if path in seen:
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        extracted = extract_defined_symbols(text, "python")
        if extracted:
            collected.extend(extracted)
    return tuple(collected)


def _resolve_existing(target: str, source_root: Path) -> Optional[Path]:
    """Read 目标 → 磁盘文件：源根 + 目标相对部分（逐级回退，取首个存在文件）。

    Windows 陷阱：``Path('/demo/x.py').is_absolute()`` 为 False（无盘符），
    因此统一按 ``parts`` 尾部拼接回退，不区分目标是否带根前缀。
    """
    parts = [p for p in Path(target).parts if p not in ("\\", "/")]
    candidates = [source_root.joinpath(*parts[n:]) for n in range(len(parts))]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def build_report_model(outcome: ScanOutcome, title: str = "") -> ReportModel:
    """ScanOutcome → ReportModel（M5 报告组装；只搬运数据，零判定，K6）。

    阈值口径从 config 运行时读取（K1 单点）；注记 = 披露制文本 + 解析/符号显式说明。
    """
    source_summary = "%d 个会话（%s）" % (
        len(outcome.sessions),
        "、".join(sorted({s.ir.meta.source for s in outcome.sessions})) or "无来源",
    )
    thresholds_note = (
        "返工：版本 ≥ %d 或编辑 ≥ %d（config.py 单点）；粗匹配相似度 ≥ %.2f"
        % (config.REWORK_MIN_VERSIONS, config.REWORK_MIN_EDITS, config.DUP_MATCH_THRESHOLD)
    )
    notes = list(outcome.report_notes)
    notes.extend("%s" % n.message for s in outcome.sessions for n in s.ir.notes if n.code)
    return ReportModel(
        meta=ReportMeta(
            title=title or ("%s 分析报告（本地生成）" % config.TOOL_NAME),
            tool_name=config.TOOL_NAME,
            tool_version=__version__,
            source_summary=source_summary,
            thresholds_note=thresholds_note,
        ),
        rework_findings=outcome.findings,
        dup_candidates=tuple(
            c for m in outcome.session_metrics for c in m.dup_candidates
        ),
        session_metrics=outcome.session_metrics,
        notes=tuple(notes),
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
