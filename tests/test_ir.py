"""统一会话 IR：确定性序列化与不可变（schema v1 锁测）。"""

import dataclasses
import json

import pytest

from agent_rework_lens import ir
from agent_rework_lens.ir import (
    KINDS,
    ParseNote,
    SessionIR,
    SessionMeta,
    ToolUseEvent,
    TokenUsageEvent,
)


def _sample() -> SessionIR:
    meta = SessionMeta(
        source="claude_code",
        session_id="s-1",
        cwd="/demo/alpha",
        started_at="2026-01-01T00:00:00Z",
        source_file="/demo/logs/s-1.jsonl",
        project_slug="demo-alpha",
    )
    events = (
        ToolUseEvent(seq=3, kind=ir.KIND_READ, tool_name="Read", timestamp="2026-01-01T00:00:01Z", file_path="/demo/alpha/src/util_a.py"),
        ToolUseEvent(seq=7, kind=ir.KIND_EDIT, tool_name="Edit", file_path="/demo/alpha/src/util_a.py"),
    )
    tokens = (TokenUsageEvent(seq=4, input_tokens=100, output_tokens=20),)
    notes = (ParseNote(code="malformed_json_line", message="坏行", count=2),)
    return SessionIR(meta=meta, tool_events=events, token_events=tokens, notes=notes)


def test_kind_registry_locked():
    assert KINDS == ("read", "edit", "write", "multiedit", "exec", "other")


def test_to_json_deterministic_bytes():
    assert _sample().to_json() == _sample().to_json()
    assert _sample().to_json().endswith("\n")


def test_to_json_roundtrip():
    data = json.loads(_sample().to_json())
    assert data["ir_version"] == 1
    assert data["meta"]["session_id"] == "s-1"
    assert data["tool_events"][0]["kind"] == "read"
    assert data["notes"][0]["count"] == 2


def test_json_key_order_stable():
    text = _sample().to_json()
    order = ['"ir_version"', '"meta"', '"notes"', '"token_events"', '"tool_events"']
    indexes = [text.index(token) for token in order]
    assert indexes == sorted(indexes)


def test_frozen_immutable():
    sample = _sample()
    with pytest.raises(dataclasses.FrozenInstanceError):
        sample.meta = None  # type: ignore[misc]


def test_unknown_fields_default_none_not_guessed():
    event = ToolUseEvent(seq=1, kind="exec", tool_name="Bash")
    assert event.file_path is None
    assert event.timestamp is None
