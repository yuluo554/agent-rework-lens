"""发现层：递归 / 过滤 / 缺源语义 / 优先级 / 确定性（FR-1）。"""

import pytest

from agent_rework_lens import config
from agent_rework_lens.discovery import (
    KIND_CLAUDE_FILE_HISTORY,
    KIND_CLAUDE_SESSIONS,
    KIND_CODEX_SESSIONS,
    discover_sources,
    resolve_claude_home,
    resolve_codex_home,
)


def _make_tree(tmp_path):
    claude = tmp_path / "claude"
    (claude / "projects" / "proj-a").mkdir(parents=True)
    (claude / "projects" / "proj-a" / "s1.jsonl").write_text("{}\n", encoding="utf-8")
    (claude / "projects" / "proj-a" / "sub").mkdir()
    (claude / "projects" / "proj-a" / "sub" / "s2.jsonl").write_text("{}\n", encoding="utf-8")
    (claude / "projects" / "proj-b").mkdir()
    (claude / "projects" / "proj-b" / "note.txt").write_text("x", encoding="utf-8")
    history = claude / "file-history" / "sess-1"
    history.mkdir(parents=True)
    (history / "aaaa@v1").write_text("", encoding="utf-8")
    (history / "aaaa@v2").write_text("", encoding="utf-8")
    codex = tmp_path / "codex"
    (codex / "sessions" / "2026" / "10" / "15").mkdir(parents=True)
    (codex / "sessions" / "2026" / "10" / "15" / "rollout-x.jsonl").write_text("{}\n", encoding="utf-8")
    return claude, codex


def test_counts_and_recursion(tmp_path):
    claude, codex = _make_tree(tmp_path)
    result = discover_sources(str(claude), str(codex))
    counts = {loc.kind: loc.file_count for loc in result.locations}
    assert counts == {
        KIND_CLAUDE_SESSIONS: 2,  # 嵌套一层也被递归发现；.txt 被过滤
        KIND_CLAUDE_FILE_HISTORY: 2,
        KIND_CODEX_SESSIONS: 1,
    }
    assert result.total_files == 5
    assert result.missing == ()


def test_missing_sources_reported_not_faked(tmp_path):
    result = discover_sources(str(tmp_path / "nope"), str(tmp_path / "nope2"))
    assert result.locations == ()
    assert {m.kind for m in result.missing} == {
        KIND_CLAUDE_SESSIONS,
        KIND_CLAUDE_FILE_HISTORY,
        KIND_CODEX_SESSIONS,
    }
    for item in result.missing:
        assert item.looked_at  # 明确"查过哪里"


def test_source_filter_limits_probe_scope(tmp_path):
    claude, codex = _make_tree(tmp_path)
    result = discover_sources(str(claude), str(codex), source_filter="codex")
    assert [loc.kind for loc in result.locations] == [KIND_CODEX_SESSIONS]
    assert all(m.kind == KIND_CODEX_SESSIONS for m in result.missing)


def test_invalid_filter_rejected(tmp_path):
    with pytest.raises(ValueError):
        discover_sources(str(tmp_path), str(tmp_path), source_filter="bogus")


def test_env_var_used_when_no_param(tmp_path, monkeypatch):
    claude, codex = _make_tree(tmp_path / "envtree")
    monkeypatch.setenv(config.ENV_CLAUDE_HOME, str(claude))
    monkeypatch.setenv(config.ENV_CODEX_HOME, str(codex))
    assert resolve_claude_home() == claude
    assert resolve_codex_home() == codex


def test_explicit_param_overrides_env(tmp_path, monkeypatch):
    env_claude, _ = _make_tree(tmp_path / "envtree")
    monkeypatch.setenv(config.ENV_CLAUDE_HOME, str(env_claude))
    override = tmp_path / "override"
    assert resolve_claude_home(str(override)) == override
    result = discover_sources(str(override), None, source_filter="claude")
    assert result.locations == ()  # override 目录不存在：未发现，不回落 env


def test_output_deterministic(tmp_path):
    claude, codex = _make_tree(tmp_path)
    first = discover_sources(str(claude), str(codex))
    second = discover_sources(str(claude), str(codex))
    assert [(loc.kind, loc.files) for loc in first.locations] == [
        (loc.kind, loc.files) for loc in second.locations
    ]
