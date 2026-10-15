"""Claude Code 会话日志解析器 → SessionIR。

字段策略（data/README.md §2.6 核对结论，全部 ✅）：
- **R1** ``@vN`` = 第 N 次编辑**前**的备份；版本链长度 = ``@vN`` 最大 N；
- **R2** 快照 = 编辑前全文副本；二进制快照按二进制计数，**不解析内容**；
- **R4** Edit input 固定 ``{file_path, old_string, new_string, replace_all}``、
  Write 固定 ``{file_path, content}``；MultiEdit 本机 0 次（D-M1-4）→ 出现即按
  "多段 Edit 序列"语义降级记 edit + ParseNote，不编造字段形态；
- **R6** 快照 entry 固定 4 字段、可含 null（容错）；快照记录 version 可高于目录现存
  → **只实读目录建链，不反推**（K4）。

未核对字段不进入计算路径 → 跳过并计 ParseNote（K7）。确定性：同输入双跑逐字节一致。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..ir import (
    KIND_EDIT,
    KIND_EXEC,
    KIND_OTHER,
    KIND_READ,
    KIND_WRITE,
    ParseNote,
    SessionIR,
    SessionMeta,
    TokenUsageEvent,
    ToolUseEvent,
)
from .common import iter_jsonl_lines

# 快照 entry 中允许出现的字段（R6：固定 4 字段，可含 null）
_SNAPSHOT_ENTRY_FIELDS = frozenset({"backupFileName", "version", "backupTime", "realParentDir"})

# 工具名 → kind（R3/R4 核对口径；NotebookEdit 与 Edit 同为"编辑"语义）
_TOOL_KINDS = {
    "Read": KIND_READ,
    "Edit": KIND_EDIT,
    "NotebookEdit": KIND_EDIT,
    "Write": KIND_WRITE,
    "MultiEdit": KIND_EDIT,  # D-M1-4：降级 + ParseNote
    "Bash": KIND_EXEC,
}


def parse_claude_session(path) -> SessionIR:
    """解析单个 Claude Code 会话 jsonl → SessionIR。"""
    path = Path(path)
    meta = SessionMeta(source="claude_code", session_id="unknown", source_file=str(path))
    tool_events: List[ToolUseEvent] = []
    token_events: List[TokenUsageEvent] = []
    notes: List[ParseNote] = []
    note_index: Dict[Tuple[str, str], int] = {}

    for line_number, obj, error in iter_jsonl_lines(path):
        if error is not None:
            _bump_note(notes, note_index, "bad_line", "第 %d 行：%s" % (line_number, error))
            continue

        if obj.get("type") == "file-history-snapshot":
            _check_snapshot(obj, notes, note_index)
            continue

        message = obj.get("message")
        if not isinstance(message, dict):
            meta = _absorb_meta(meta, obj)
            continue

        if message.get("role") != "assistant":
            continue

        usage = message.get("usage")
        if isinstance(usage, dict):
            token_events.append(_parse_usage(line_number, obj.get("timestamp"), usage))

        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            event = _classify_tool_use(block, line_number, obj.get("timestamp"))
            if event is None:
                _bump_note(
                    notes,
                    note_index,
                    "unverified_field_skipped",
                    "第 %d 行：tool_use 缺 name/input，未核对不启用（K7）" % line_number,
                )
                continue
            if event.tool_name == "MultiEdit":
                _bump_note(
                    notes,
                    note_index,
                    "multiedit_downgraded",
                    "第 %d 行：MultiEdit 本机未核对（D-M1-4），按 edit 序列降级计数" % line_number,
                )
            tool_events.append(event)

    return SessionIR(
        meta=meta,
        tool_events=tuple(tool_events),
        token_events=tuple(token_events),
        notes=tuple(notes),
    )


def _absorb_meta(meta: SessionMeta, obj: dict) -> SessionMeta:
    """从非消息行吸收会话级元数据（只取已核对字段；缺失保持 None，不猜测）。"""
    if isinstance(obj.get("sessionId"), str) and meta.session_id == "unknown":
        meta = _replace_meta(meta, session_id=obj["sessionId"])
    if isinstance(obj.get("cwd"), str) and meta.cwd is None:
        meta = _replace_meta(meta, cwd=obj["cwd"])
    if (
        isinstance(obj.get("timestamp"), str)
        and meta.started_at is None
        and obj.get("type") in (None, "session_meta", "session_meta_like")
    ):
        meta = _replace_meta(meta, started_at=obj["timestamp"])
    if isinstance(obj.get("version"), str) and meta.agent_version is None:
        meta = _replace_meta(meta, agent_version=obj["version"])
    return meta


def _replace_meta(meta: SessionMeta, **changes) -> SessionMeta:
    fields = {
        "source": meta.source,
        "session_id": meta.session_id,
        "cwd": meta.cwd,
        "started_at": meta.started_at,
        "source_file": meta.source_file,
        "project_slug": meta.project_slug,
        "agent_version": meta.agent_version,
    }
    fields.update(changes)
    return SessionMeta(**fields)


def _classify_tool_use(block: dict, line_number: int, timestamp) -> Optional[ToolUseEvent]:
    name = block.get("name")
    input_data = block.get("input")
    if not isinstance(name, str) or not isinstance(input_data, dict):
        return None
    file_path = input_data.get("file_path")
    kind = _TOOL_KINDS.get(name, KIND_OTHER)
    return ToolUseEvent(
        seq=line_number,
        kind=kind,
        tool_name=name,
        timestamp=timestamp if isinstance(timestamp, str) else None,
        file_path=file_path if isinstance(file_path, str) else None,
    )


def _check_snapshot(obj: dict, notes: List[ParseNote], note_index: Dict[Tuple[str, str], int]) -> None:
    """快照行：只做形态校验与计数（R2 不解析内容、R6 容错），不产事件。"""
    snapshot = obj.get("snapshot")
    if not isinstance(snapshot, dict):
        return
    tracked = snapshot.get("trackedFileBackups")
    if not isinstance(tracked, dict):
        return
    for entry in tracked.values():
        if entry is None:
            _bump_note(notes, note_index, "snapshot_entry_null", "快照 entry 为 null（R6 容错）")
            continue
        if not isinstance(entry, dict):
            _bump_note(notes, note_index, "snapshot_entry_shape", "快照 entry 形态异常（非 dict）")
            continue
        unknown = sorted(set(entry) - _SNAPSHOT_ENTRY_FIELDS)
        if unknown:
            _bump_note(
                notes,
                note_index,
                "snapshot_entry_extra_field",
                "快照 entry 含未核对字段 %s（K7：跳过不启用）" % ",".join(unknown),
            )


def _parse_usage(seq: int, timestamp, usage: dict) -> TokenUsageEvent:
    def _int(value):
        return value if isinstance(value, int) else None

    input_tokens = _int(usage.get("input_tokens"))
    output_tokens = _int(usage.get("output_tokens"))
    total = None
    if input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    return TokenUsageEvent(
        seq=seq,
        timestamp=timestamp if isinstance(timestamp, str) else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=_int(usage.get("cache_creation_input_tokens")),
        cache_read_input_tokens=_int(usage.get("cache_read_input_tokens")),
        total_tokens=total,
    )


def _bump_note(notes: List[ParseNote], index: Dict[Tuple[str, str], int], code: str, message: str) -> None:
    key = (code, message)
    pos = index.get(key)
    if pos is not None:
        notes[pos] = ParseNote(code=code, message=message, count=notes[pos].count + 1)
    else:
        index[key] = len(notes)
        notes.append(ParseNote(code=code, message=message, count=1))


# ── file-history 实读（版本链；K4：只实读不反推） ─────────────────────────


# ── 会话文件快照实读（R6：file_path → backupFileName 关联键，引擎用） ──────


def read_snapshot_file_map(session_path) -> Dict[str, dict]:
    """实读单个会话 jsonl 的快照行 → ``{file_path: {backup_stem, max_version}}``。

    依据 R6：``trackedFileBackups`` 键 = 被跟踪真实文件路径，entry 的
    ``backupFileName``（如 ``89b13e3cd80c18a9@v1``）精确命中
    ``file-history/<session-uuid>/<backupFileName>`` → 关联键 = backupFileName。
    只取已核对字段（``backupFileName`` / ``version``，K7）；``version`` 高于文件名
    内嵌 N 时以文件名为准（R1：``@vN`` 文件名是唯一可用证据）；无 ``@vN`` 形态的
    backupFileName → 证据不可用，跳过（同 K4 纪律，不猜测）。
    """
    session_path = Path(session_path)
    version_re = re.compile(r"@v(\d+)(?:\.[^@\\/]*)?$")
    latest: Dict[str, dict] = {}
    for _line_number, obj, error in iter_jsonl_lines(session_path):
        if error is not None or not isinstance(obj, dict):
            continue
        if obj.get("type") != "file-history-snapshot":
            continue
        snapshot = obj.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        tracked = snapshot.get("trackedFileBackups")
        if not isinstance(tracked, dict):
            continue
        for file_path, entry in tracked.items():
            if not isinstance(file_path, str) or not isinstance(entry, dict):
                continue
            backup_name = entry.get("backupFileName")
            if not isinstance(backup_name, str):
                continue
            match = version_re.search(backup_name)
            if not match:
                continue
            stem = backup_name[: match.start()]
            version = int(match.group(1))
            current = latest.get(file_path)
            if current is None or version > current["max_version"]:
                latest[file_path] = {"backup_stem": stem, "max_version": version}
    return latest


def read_version_chains(history_dir) -> Dict[str, Dict[str, dict]]:
    """实读 ``<claude_home>/file-history/<session uuid>/`` → 版本链结构。

    返回 ``{session_id: {hash_stem: {"versions": (N, ...), "files": (路径, ...), "max_version": N}}}``。
    证据 = 目录中实际存在的 ``<hash>@vN`` 文件名（R1/R6）；记录版本高于目录现存时以目录为准。
    """
    history_dir = Path(history_dir)
    result: Dict[str, Dict[str, dict]] = {}
    if not history_dir.is_dir():
        return result
    version_re = re.compile(r"@v(\d+)(?:\.[^@\\/]*)?$")
    for session_dir in sorted(history_dir.iterdir(), key=str):
        if not session_dir.is_dir():
            continue
        chains: Dict[str, List[dict]] = {}
        for f in sorted(session_dir.iterdir(), key=str):
            if not f.is_file():
                continue
            match = version_re.search(f.name)
            if not match:
                continue
            stem = f.name[: match.start()]
            if not stem:
                continue
            chains.setdefault(stem, []).append(
                {"version": int(match.group(1)), "path": str(f)}
            )
        if not chains:
            continue
        result[session_dir.name] = {
            stem: {
                "versions": tuple(sorted(item["version"] for item in items)),
                "files": tuple(item["path"] for item in sorted(items, key=lambda x: x["path"])),
                "max_version": max(item["version"] for item in items),
            }
            for stem, items in sorted(chains.items())
        }
    return result
