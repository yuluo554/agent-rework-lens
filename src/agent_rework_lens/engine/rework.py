"""返工检测引擎（plan/04 §7.1 口径，M3 实现）。

判定语义（口径，plan/04 §7.1）：
1. 版本数 ≥ N 或 Edit 次数 ≥ M（阈值见 config.py 单点）→ ``rework``；
2. 两条都不成立且**版本链缺失** → ``insufficient_data``（禁止由 Edit 次数反推版本链，K4）；
3. 两条都不成立且版本链存在 → ``not_rework``。

版本数证据（K4：只实读不反推）：
- Claude：``file-history`` 目录实读链（``read_version_chains``）+ 会话快照行的
  ``backupFileName`` 关联（R6，``read_snapshot_file_map``）；两者按 hash stem 对齐，
  以目录现存为准（快照记录版本可高于目录现存 → 不取大，R6/K4）。
- Codex：无 file-history 源（R5）→ 版本数恒缺失，返工判据以 apply_patch 写事件计数
  为主（truth 口径 ``reason: "edits"``）；链缺失但判据 2 已由编辑数满足时不判
  insufficient_data（不反推，只按事件计数判 rework / not_rework）。

链缺失语义（与合成真值对齐）：同一文件既有 Write（新建）又被 Edit 过 → 新建后
的编辑从 v1 起备份，缺链只可能因 file-history 不可用，判 ``insufficient_data``；
纯 Write 新建无链属正常（首次写不备份），判 ``not_rework``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .. import config
from ..ir import KIND_EDIT, KIND_WRITE, SessionIR, ToolUseEvent

VERDICT_REWORK = "rework"
VERDICT_NOT_REWORK = "not_rework"
VERDICT_INSUFFICIENT = "insufficient_data"
VERDICTS = (VERDICT_REWORK, VERDICT_NOT_REWORK, VERDICT_INSUFFICIENT)

REASON_VERSIONS = "versions>=N"
REASON_EDITS = "edits>=M"
REASON_NO_HIT = "both_below_threshold"
REASON_CHAIN_MISSING = "version_chain_missing"


@dataclass(frozen=True)
class ReworkFinding:
    """单个文件（单会话内）的返工判定结果；``evidence`` 为证据锚点（源文件行号 / 版本文件名）。"""

    file_path: str
    session_id: str
    verdict: str  # VERDICTS 之一
    version_count: Optional[int] = None  # 版本链缺失 → None（不猜测）
    edit_count: int = 0
    first_edit_seq: Optional[int] = None
    last_edit_seq: Optional[int] = None
    span_seconds: Optional[float] = None  # 时间戳缺失 → None（报告注明）
    reasons: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _span_seconds(events: Tuple[ToolUseEvent, ...]) -> Optional[float]:
    times = [_parse_timestamp(e.timestamp) for e in events]
    times = [t for t in times if t is not None]
    if len(times) < 2:
        return None
    return (max(times) - min(times)).total_seconds()


def _group_writes(ir: SessionIR) -> Dict[str, Tuple[ToolUseEvent, ...]]:
    """按 file_path 分组写事件（edit/write/multiedit）；file_path 缺失 → 不归属（跳过）。"""
    grouped: Dict[str, List[ToolUseEvent]] = {}
    for event in ir.tool_events:
        if event.kind not in (KIND_EDIT, KIND_WRITE):
            continue
        if not event.file_path:
            continue
        grouped.setdefault(event.file_path, []).append(event)
    return {path: tuple(events) for path, events in grouped.items()}


def _claude_version_count(
    file_path: str,
    session_chains: Dict[str, dict],
    snapshot_map: Dict[str, dict],
) -> Optional[int]:
    """目录实读链 + 快照 backupFileName 关联（R6）；对不上 → None（不反推，K4）。"""
    mapping = snapshot_map.get(file_path)
    if mapping is None:
        return None
    chain = session_chains.get(mapping["backup_stem"])
    if chain is None:
        return None
    versions = chain.get("versions") or ()
    return len(versions)


def analyze_rework(
    ir: SessionIR,
    version_chains: Optional[Dict[str, dict]] = None,
    snapshot_file_map: Optional[Dict[str, dict]] = None,
) -> Tuple[ReworkFinding, ...]:
    """对会话 IR 的每个被编辑/新建文件给出返工判定（确定性，不读时钟，K11）。

    ``version_chains`` = ``read_version_chains()[session_id]``（Claude 源；Codex 传空）；
    ``snapshot_file_map`` = ``read_snapshot_file_map(会话文件)``（Claude 源；Codex 传空）。
    """
    version_chains = version_chains or {}
    snapshot_file_map = snapshot_file_map or {}
    findings: List[ReworkFinding] = []
    for file_path, events in sorted(_group_writes(ir).items()):
        write_events = tuple(e for e in events if e.kind == KIND_WRITE)
        edit_events = tuple(e for e in events if e.kind == KIND_EDIT)
        edit_count = len(events)
        version_count = _claude_version_count(file_path, version_chains, snapshot_file_map)
        chain_missing = version_count is None

        reasons = []
        hit_versions = version_count is not None and version_count >= config.REWORK_MIN_VERSIONS
        hit_edits = edit_count >= config.REWORK_MIN_EDITS
        if hit_versions:
            reasons.append(REASON_VERSIONS)
        if hit_edits:
            reasons.append(REASON_EDITS)

        if hit_versions or hit_edits:
            verdict = VERDICT_REWORK
        elif chain_missing and not write_events:
            # 无 Write（非新建）且无链：Edit 的"编辑前备份"应存在但缺失 → 证据不足（K4）
            verdict = VERDICT_INSUFFICIENT
            reasons.append(REASON_CHAIN_MISSING)
        else:
            verdict = VERDICT_NOT_REWORK
            reasons.append(REASON_NO_HIT)

        ordered = tuple(events)
        evidence = ["%s:%d" % (ir.meta.source_file, e.seq) for e in ordered]
        if version_count is not None:
            mapping = snapshot_file_map.get(file_path) or {}
            stem = mapping.get("backup_stem", "")
            if stem:
                evidence.append("%s@v%d" % (stem, version_count))
        findings.append(
            ReworkFinding(
                file_path=file_path,
                session_id=ir.meta.session_id,
                verdict=verdict,
                version_count=version_count,
                edit_count=edit_count,
                first_edit_seq=ordered[0].seq,
                last_edit_seq=ordered[-1].seq,
                span_seconds=_span_seconds(ordered),
                reasons=tuple(reasons),
                evidence=tuple(evidence),
            )
        )
    return tuple(findings)
