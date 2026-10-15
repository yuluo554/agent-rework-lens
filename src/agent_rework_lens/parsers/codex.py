"""Codex 会话日志解析器 → SessionIR。

字段策略（data/README.md §2.6 核对结论）：
- **R3** 目标文件路径在 ``payload.input``（V4A 文本）``*** Update/Add File: <path>``
  指令行内（**不在 JSON arguments 里**）；``payload.type`` 有 function_call /
  custom_tool_call 两种容器；
- **R5** ``apply_patch`` 是 Codex 唯一写文件工具 = Codex 侧编辑计数主证据；
  ``exec`` 只按执行事件计（路径不提取——exec 命令串未核对，K7）。

未核对字段不进入计算路径 → 跳过并计 ParseNote。确定性：同输入双跑逐字节一致。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..ir import (
    KIND_EXEC,
    KIND_OTHER,
    KIND_WRITE,
    ParseNote,
    SessionIR,
    SessionMeta,
    TokenUsageEvent,
    ToolUseEvent,
)
from .common import iter_jsonl_lines

# V4A 补丁指令行（R3 核对口径）：目标路径 = 指令行内路径，非 JSON arguments
_V4A_FILE_RE = re.compile(r"^\*\*\* (Update|Add) File: (.+?)\s*$")

_APPLY_PATCH = "apply_patch"


def parse_codex_session(path) -> SessionIR:
    """解析单个 Codex 会话 jsonl → SessionIR。"""
    path = Path(path)
    meta = SessionMeta(source="codex", session_id="unknown", source_file=str(path))
    tool_events: List[ToolUseEvent] = []
    token_events: List[TokenUsageEvent] = []
    notes: List[ParseNote] = []
    note_index: Dict[Tuple[str, str], int] = {}

    for line_number, obj, error in iter_jsonl_lines(path):
        if error is not None:
            _bump_note(notes, note_index, "bad_line", "第 %d 行：%s" % (line_number, error))
            continue

        line_type = obj.get("type")
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            continue

        timestamp = obj.get("timestamp")
        timestamp = timestamp if isinstance(timestamp, str) else None
        payload_type = payload.get("type")

        if line_type == "session_meta":
            sid = payload.get("session_id") or payload.get("id")
            if isinstance(sid, str):
                meta = _replace_meta(meta, session_id=sid)
            if isinstance(payload.get("cwd"), str):
                meta = _replace_meta(meta, cwd=payload["cwd"])
            if isinstance(payload.get("cli_version"), str):
                meta = _replace_meta(meta, agent_version=payload["cli_version"])
            if meta.started_at is None and isinstance(payload.get("timestamp"), str):
                meta = _replace_meta(meta, started_at=payload["timestamp"])
            continue

        if payload_type == "function_call":
            name = payload.get("name")
            if name == "exec":
                # exec 命令串未进入路径级计算（K7：arguments 内容未核对为路径证据）
                tool_events.append(
                    ToolUseEvent(seq=line_number, kind=KIND_EXEC, tool_name="exec", timestamp=timestamp)
                )
            else:
                tool_events.append(
                    ToolUseEvent(
                        seq=line_number,
                        kind=KIND_OTHER,
                        tool_name=name if isinstance(name, str) else "unknown",
                        timestamp=timestamp,
                    )
                )
            continue

        if payload_type == "custom_tool_call" and payload.get("name") == _APPLY_PATCH:
            paths = _extract_patch_paths(payload.get("input"))
            if paths is None:
                _bump_note(
                    notes,
                    note_index,
                    "apply_patch_input_missing",
                    "第 %d 行：apply_patch 缺 V4A 文本 input，跳过路径提取（K7）" % line_number,
                )
                paths = []
            for file_path in paths:
                tool_events.append(
                    ToolUseEvent(
                        seq=line_number,
                        kind=KIND_WRITE,
                        tool_name=_APPLY_PATCH,
                        timestamp=timestamp,
                        file_path=file_path,
                    )
                )
            if not paths:
                # 无可提取路径仍计一次写事件（编辑计数主证据 R5；路径 unknown）
                tool_events.append(
                    ToolUseEvent(
                        seq=line_number,
                        kind=KIND_WRITE,
                        tool_name=_APPLY_PATCH,
                        timestamp=timestamp,
                        file_path=None,
                    )
                )
            continue

        if payload_type == "event_msg":
            token_payload = payload.get("payload")
            if isinstance(token_payload, dict):
                token_events.append(_parse_usage(line_number, timestamp, token_payload))
            continue

        # 未核对的 payload.type：跳过并显式注记（K7；含 R3 提到的其他容器形态）
        _bump_note(
            notes,
            note_index,
            "unverified_payload_type_skipped",
            "第 %d 行：payload.type=%r 未核对不启用（K7）" % (line_number, payload_type),
        )

    return SessionIR(
        meta=meta,
        tool_events=tuple(tool_events),
        token_events=tuple(token_events),
        notes=tuple(notes),
    )


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


def _extract_patch_paths(input_value) -> Optional[List[str]]:
    """从 V4A 补丁文本提取 Update/Add File 目标路径（按出现顺序，确定性）。

    input 非 str → None（调用方计 ParseNote）；无可提取行 → []。
    """
    if not isinstance(input_value, str):
        return None
    paths: List[str] = []
    for line in input_value.splitlines():
        match = _V4A_FILE_RE.match(line)
        if match:
            paths.append(match.group(2).strip())
    return paths


def _parse_usage(seq: int, timestamp, usage: dict) -> TokenUsageEvent:
    def _int(value):
        return value if isinstance(value, int) else None

    input_tokens = _int(usage.get("input_tokens"))
    output_tokens = _int(usage.get("output_tokens"))
    cached = _int(usage.get("input_tokens_cached"))
    total = _int(usage.get("total_token_counts")) or (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    return TokenUsageEvent(
        seq=seq,
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cached,
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
