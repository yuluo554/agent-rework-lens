"""M3 引擎回归：truth 驱动逐例对账 + 反例 + 阈值单点 + 锚点字段（plan/06 M3 DoD）。"""

import json
from pathlib import Path

import pytest

from agent_rework_lens import config
from agent_rework_lens.engine import metrics, rework, symbols
from agent_rework_lens.engine.rework import (
    REASON_CHAIN_MISSING,
    REASON_EDITS,
    REASON_NO_HIT,
    REASON_VERSIONS,
    VERDICT_INSUFFICIENT,
    VERDICT_NOT_REWORK,
    VERDICT_REWORK,
    analyze_rework,
)
from agent_rework_lens.ir import KIND_EDIT, KIND_READ, KIND_WRITE
from agent_rework_lens.parsers import parse_claude_session, parse_codex_session
from agent_rework_lens.parsers.claude_code import read_snapshot_file_map, read_version_chains

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = REPO_ROOT / "data" / "synthetic" / "samples"


def _iter_cases():
    return sorted(p for p in SAMPLES.iterdir() if p.is_dir())


def _engine_inputs(case_dir):
    """case 目录 → (ir, session_chains, snapshot_map, truth)。"""
    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    session_path = case_dir / "session.jsonl"
    if truth["source"] == "claude_code":
        ir = parse_claude_session(session_path)
        chains = read_version_chains(case_dir / "file-history")
        snap_map = read_snapshot_file_map(session_path)
        return ir, chains.get(ir.meta.session_id, {}), snap_map, truth
    ir = parse_codex_session(session_path)
    return ir, {}, {}, truth


def _expected_status(truth) -> str:
    if truth.get("expected_rework"):
        return VERDICT_REWORK
    if truth.get("expect_status") == "insufficient_data":
        return VERDICT_INSUFFICIENT
    return VERDICT_NOT_REWORK


# ── 逐例 truth 对账（11 case 全量） ───────────────────────────────────────


@pytest.mark.parametrize("case_dir", _iter_cases(), ids=lambda p: p.name)
def test_engine_matches_truth(case_dir):
    loaded = _engine_inputs(case_dir)
    if loaded is None:
        pytest.skip("非会话样例目录")
    ir, chains, snap_map, truth = loaded
    findings = analyze_rework(ir, chains, snap_map)
    by_file = {f.file_path: f for f in findings}

    expected_status = _expected_status(truth)
    # 每个期望文件都产生 finding 且 verdict 符合 case 语义
    expected_files = [
        item["file"] for item in truth.get("expected_rework", [])
    ] + [
        item["file"] for item in truth.get("expected_normal", []) if "file" in item
    ]
    if truth["case_type"] == "missing_chain":
        # 写事件的 file_path 来自 Edit input；同上按 file 记录
        expected_files = ["/demo/beta/src/alpha_b.py"]
    if truth["case_type"] == "duplicate":
        # duplicate case 的 truth 只标符号候选，不标文件：仅验证不误判 rework
        expected_files = list(by_file)
    assert expected_files, "truth 应指明被写文件"
    for file_path in expected_files:
        assert file_path in by_file, "%s 应产生 finding" % file_path
        assert by_file[file_path].verdict == expected_status, (
            "%s: verdict=%s 期望 %s（reasons=%s）"
            % (file_path, by_file[file_path].verdict, expected_status, by_file[file_path].reasons)
        )

    # rework 命中项：edit_count / version_count / reason 对账
    for item in truth.get("expected_rework", []):
        finding = by_file[item["file"]]
        assert finding.edit_count == item["edit_count"]
        if item["reason"] == "versions":
            assert finding.version_count is not None
            assert finding.version_count >= item["min_versions"]
            assert REASON_VERSIONS in finding.reasons
        else:  # edits（Codex apply_patch 计数）
            assert REASON_EDITS in finding.reasons
        # also_expect 的链观察值
        also = truth.get("also_expect", {}).get(item["file"], {})
        if "version_chain_observed" in also and finding.version_count is not None:
            assert finding.version_count == also["version_chain_observed"]

    # not_rework 项：edit_count 对账 + 不持 rework 理由
    for item in truth.get("expected_normal", []):
        finding = by_file[item["file"]]
        assert finding.edit_count == item["edit_count"]
        assert REASON_VERSIONS not in finding.reasons
        assert REASON_EDITS not in finding.reasons

    # insufficient_data：链缺失显式成理由，version_count=None（K4 不猜测）
    if truth["case_type"] == "missing_chain":
        finding = next(iter(by_file.values()))
        assert finding.verdict == VERDICT_INSUFFICIENT
        assert finding.version_count is None
        assert REASON_CHAIN_MISSING in finding.reasons


# ── 锚点字段与时间跨度 ────────────────────────────────────────────────────


def test_finding_evidence_anchors_and_span():
    ir, chains, snap_map, _ = _engine_inputs(SAMPLES / "case-claude_code-rework-01")
    findings = analyze_rework(ir, chains, snap_map)
    assert len(findings) == 1
    finding = findings[0]
    # 锚点 = (源文件, 行号 seq) 三元组前两半 + 版本文件名
    assert finding.evidence and all(
        ev.startswith(ir.meta.source_file + ":") or "@v" in ev for ev in finding.evidence
    )
    assert finding.first_edit_seq == 4  # 首个写事件在源文件第 4 行
    assert finding.last_edit_seq == 10
    # 会话时间戳齐备 → span = 09:10 → 09:30 = 1200s
    assert finding.span_seconds == 1200.0


def test_span_none_when_timestamps_missing():
    ir, chains, snap_map, _ = _engine_inputs(SAMPLES / "case-claude_code-rework-01")
    from agent_rework_lens.ir import SessionMeta, SessionIR, ToolUseEvent

    bare = SessionIR(
        meta=SessionMeta(source="claude_code", session_id="s"),
        tool_events=(
            ToolUseEvent(seq=1, kind=KIND_EDIT, tool_name="Edit", file_path="/x.py"),
            ToolUseEvent(seq=2, kind=KIND_EDIT, tool_name="Edit", file_path="/x.py"),
        ),
    )
    finding = analyze_rework(bare, {}, {})[0]
    assert finding.span_seconds is None  # 时间戳缺失 → None（报告注明）


def test_single_write_new_file_is_not_rework_even_without_chain():
    """normal-01：纯 Write 新建无链 → not_rework（新建首写不备份，非证据缺失）。"""
    ir, chains, snap_map, _ = _engine_inputs(SAMPLES / "case-claude_code-normal-01")
    findings = analyze_rework(ir, chains, snap_map)
    assert len(findings) == 1
    assert findings[0].verdict == VERDICT_NOT_REWORK
    assert findings[0].version_count is None
    assert REASON_NO_HIT in findings[0].reasons


# ── 阈值单点（K1）：改动一处 → 全链路同变 ────────────────────────────────


def test_threshold_edits_change_flips_verdict_everywhere(monkeypatch):
    """把 M 提到 99 → near_miss（1 次 Edit）仍不命中；把 M 降到 1 → 立即命中。"""
    ir, chains, snap_map, _ = _engine_inputs(SAMPLES / "case-claude_code-near_miss-01")
    monkeypatch.setattr(config, "REWORK_MIN_EDITS", 99)
    assert analyze_rework(ir, chains, snap_map)[0].verdict == VERDICT_NOT_REWORK
    monkeypatch.setattr(config, "REWORK_MIN_EDITS", 1)
    finding = analyze_rework(ir, chains, snap_map)[0]
    assert finding.verdict == VERDICT_REWORK
    assert REASON_EDITS in finding.reasons


def test_threshold_versions_change_flips_verdict(monkeypatch):
    ir, chains, snap_map, _ = _engine_inputs(SAMPLES / "case-claude_code-rework-01")
    monkeypatch.setattr(config, "REWORK_MIN_VERSIONS", 99)
    finding = analyze_rework(ir, chains, snap_map)[0]
    # 编辑数 3 ≥ M(3) 仍命中，但不再持 versions 理由（单点改动只影响其自有判据）
    assert REASON_VERSIONS not in finding.reasons
    monkeypatch.setattr(config, "REWORK_MIN_VERSIONS", 1)
    assert REASON_VERSIONS in analyze_rework(ir, chains, snap_map)[0].reasons


def test_dup_threshold_change_affects_matching(monkeypatch):
    # 归一化后仍不同、原始 ratio ≈ 0.74：阈值 <0.74 → 命中 high_similarity；≥0.74 → None
    monkeypatch.setattr(config, "DUP_MATCH_THRESHOLD", 0.7)
    reason, similarity = metrics.match_symbols("compute_alphax", "compute_betax")
    assert reason == "high_similarity" and similarity is not None
    monkeypatch.setattr(config, "DUP_MATCH_THRESHOLD", 0.8)
    assert metrics.match_symbols("compute_alphax", "compute_betax") is None


# ── duplicate case 引擎侧对账（新写符号 × 已有文件符号） ─────────────────


def test_duplicate_case_symbols_match_truth():
    case = SAMPLES / "case-claude_code-duplicate-01"
    ir, chains, snap_map, truth = _engine_inputs(case)
    # 从 Write 载荷提取新符号（与解析器无关的引擎单测路径：直接读 session input content）
    new_payloads = _write_payloads(case / "session.jsonl")
    new_syms = metrics.symbols_from_write_payloads(new_payloads)
    existing_syms = _project_symbols(case / "project")
    candidates = metrics.find_dup_candidates(new_syms, existing_syms, "session:4", "project/common.py:1")
    expected = truth["expected_dup_candidates"]
    assert len(candidates) == len(expected)
    for cand, exp in zip(candidates, expected):
        assert (cand.new_symbol, cand.existing_symbol, cand.match_reason) == (
            exp["new_symbol"],
            exp["existing_symbol"],
            exp["reason"],
        )


def _write_payloads(session_path):
    payloads = []
    for line in session_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("type") != "assistant":
            continue
        for block in (obj.get("message") or {}).get("content") or []:
            if block.get("type") == "tool_use" and block.get("name") == "Write":
                content = (block.get("input") or {}).get("content")
                if isinstance(content, str):
                    payloads.append(("python", content))
    return payloads


def _project_symbols(project_dir):
    collected = []
    for py_file in sorted(project_dir.rglob("*.py")):
        extracted = symbols.extract_defined_symbols(
            py_file.read_text(encoding="utf-8"), "python"
        )
        if extracted:
            collected.extend(extracted)
    return collected
