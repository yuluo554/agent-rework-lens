"""M2 解析层回归：合成样例逐例（truth 驱动）+ 确定性对账 + 容错（plan/06 M2 DoD）。"""

import json
from pathlib import Path

import pytest

from agent_rework_lens.ir import (
    KIND_EDIT,
    KIND_EXEC,
    KIND_READ,
    KIND_WRITE,
    IR_VERSION,
)
from agent_rework_lens.pipeline import run_scan
from agent_rework_lens.parsers import parse_claude_session, parse_codex_session
from agent_rework_lens.parsers.claude_code import read_version_chains

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = REPO_ROOT / "data" / "synthetic" / "samples"

# kind 口径集合（与 config.WRITE_EVENT_KINDS 语义一致；此处锁解析器输出侧）
_WRITE_KINDS = frozenset({"edit", "write", "multiedit"})


def _iter_cases():
    return sorted(p for p in SAMPLES.iterdir() if p.is_dir())


def _load_case(case_dir):
    session_path = case_dir / "session.jsonl"
    if not session_path.exists():
        return None
    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    source = truth["source"]
    parse = parse_claude_session if source == "claude_code" else parse_codex_session
    ir = parse(session_path)
    chains = read_version_chains(case_dir / "file-history") if source == "claude_code" else {}
    return ir, chains, truth


# ── 逐例回归（truth 驱动） ────────────────────────────────────────────────


@pytest.mark.parametrize("case_dir", _iter_cases(), ids=lambda p: p.name)
def test_synthetic_case_parses_to_truth(case_dir):
    loaded = _load_case(case_dir)
    if loaded is None:
        pytest.skip("非会话样例目录")
    ir, chains, truth = loaded

    # 会话标识与会话源一致（session uuid 为合成白名单形态）
    assert ir.meta.source == truth["source"]
    assert ir.meta.session_id == truth["session_id"]
    assert ir.ir_version == IR_VERSION

    # 写事件计数 = truth 期望的逐文件 edit_count 之和
    expected_writes = sum(
        item["edit_count"] for item in truth.get("also_expect", {}).values()
        if isinstance(item, dict) and "edit_count" in item
    )
    expected_writes += sum(
        item["edit_count"] for item in truth.get("expected_normal", []) if "edit_count" in item
    )
    if expected_writes:
        writes = [e for e in ir.tool_events if e.kind in _WRITE_KINDS]
        assert len(writes) == expected_writes

    # rework 期望：该文件被反复编辑 → 对应写事件 file_path 一致
    for item in truth.get("expected_rework", []):
        writes_on_file = [
            e for e in ir.tool_events if e.kind in _WRITE_KINDS and e.file_path == item["file"]
        ]
        assert len(writes_on_file) == item["edit_count"]

    # Claude 源：版本链只实读（K4）——expected_rework 标 min_versions 时链必须 ≥ 它；
    # missing_chain 无 file-history 目录 → 链为空（不得由 Edit 次数反推）
    if truth["source"] == "claude_code":
        total_versions = sum(c["max_version"] for c in chains.get(ir.meta.session_id, {}).values())
        if truth.get("expected_rework"):
            assert total_versions >= truth["expected_rework"][0]["min_versions"]
        if truth["case_type"] == "missing_chain":
            assert total_versions == 0
        if truth["case_type"] == "single_edit":
            assert total_versions == 1


def test_claude_rework01_exact_counts():
    """rework-01：3 次 Edit + 版本链 3（@v1..@v3，R1 语义）。"""
    ir, chains, truth = _load_case(SAMPLES / "case-claude_code-rework-01")
    writes = [e for e in ir.tool_events if e.kind == KIND_EDIT]
    assert len(writes) == 3
    reads = [e for e in ir.tool_events if e.kind == KIND_READ]
    assert len(reads) == 1
    chain = chains[truth["session_id"]]
    assert len(chain) == 1
    stem_chain = next(iter(chain.values()))
    assert stem_chain["versions"] == (1, 2, 3)
    assert stem_chain["max_version"] == 3


def test_codex_rework03_apply_patch_paths():
    """codex-rework-03：apply_patch 4 次（R5 编辑主证据），路径来自 V4A 指令行（R3）。"""
    ir = parse_codex_session(SAMPLES / "case-codex-rework-03" / "session.jsonl")
    writes = [e for e in ir.tool_events if e.kind == KIND_WRITE]
    assert len(writes) == 4
    assert all(e.tool_name == "apply_patch" for e in writes)
    assert {e.file_path for e in writes} == {"/demo/alpha/src/alpha_a.py"}
    execs = [e for e in ir.tool_events if e.kind == KIND_EXEC]
    assert len(execs) == 4


def test_codex_normal02_add_file_path():
    ir = parse_codex_session(SAMPLES / "case-codex-normal-02" / "session.jsonl")
    writes = [e for e in ir.tool_events if e.kind == KIND_WRITE]
    assert len(writes) == 1
    assert writes[0].file_path == "/demo/alpha/src/beta_b.py"


# ── 确定性：双跑 IR 逐字节一致（K3/K11） ──────────────────────────────────


@pytest.mark.parametrize("case_dir", _iter_cases(), ids=lambda p: p.name)
def test_ir_double_run_byte_identical(case_dir):
    loaded = _load_case(case_dir)
    if loaded is None:
        pytest.skip("非会话样例目录")
    ir, _, _ = loaded
    session_path = case_dir / "session.jsonl"
    parse = parse_claude_session if ir.meta.source == "claude_code" else parse_codex_session
    again = parse(session_path)
    assert ir == again
    assert ir.to_json() == again.to_json()


def test_run_scan_double_run_byte_identical(tmp_path):
    """端到端：把 3 个代表性 case 复制到临时 home，run_scan 双跑输出逐字节一致。"""
    home = tmp_path / "claude"
    for name in ("case-claude_code-rework-01", "case-claude_code-single_edit-01"):
        case = SAMPLES / name
        sid = json.loads((case / "truth.json").read_text(encoding="utf-8"))["session_id"]
        (home / "projects" / sid).mkdir(parents=True)
        (home / "projects" / sid / "session.jsonl").write_bytes((case / "session.jsonl").read_bytes())
        hist = home / "file-history" / sid
        if (case / "file-history" / sid).exists():
            hist.mkdir(parents=True)
            for f in (case / "file-history" / sid).iterdir():
                (hist / f.name).write_bytes(f.read_bytes())
    codex = tmp_path / "codex"
    case = SAMPLES / "case-codex-rework-03"
    sid = json.loads((case / "truth.json").read_text(encoding="utf-8"))["session_id"]
    (codex / "sessions" / sid).mkdir(parents=True)
    (codex / "sessions" / sid / "session.jsonl").write_bytes((case / "session.jsonl").read_bytes())

    def _run():
        outcome = run_scan(str(home), str(codex))
        return json.dumps(
            {
                "sessions": [s.ir.to_dict() for s in outcome.sessions],
                "chains": {
                    sid: {stem: dict(c) for stem, c in stems.items()}
                    for sid, stems in outcome.version_chains.items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

    assert _run() == _run()


def test_run_scan_counts_and_chains(tmp_path):
    home = tmp_path / "claude"
    case = SAMPLES / "case-claude_code-rework-01"
    sid = json.loads((case / "truth.json").read_text(encoding="utf-8"))["session_id"]
    (home / "projects" / sid).mkdir(parents=True)
    (home / "projects" / sid / "session.jsonl").write_bytes((case / "session.jsonl").read_bytes())
    (home / "file-history" / sid).mkdir(parents=True)
    for f in (case / "file-history" / sid).iterdir():
        (home / "file-history" / sid / f.name).write_bytes(f.read_bytes())

    outcome = run_scan(str(home), str(tmp_path / "codex"))
    assert len(outcome.sessions) == 1
    session = outcome.sessions[0]
    assert session.session_id == sid
    assert session.write_event_count == 3
    assert len(session.version_chains) == 1
    stem_chain = next(iter(session.version_chains.values()))
    assert stem_chain["max_version"] == 3
    # scan 摘要零判定：引擎结论字段不存在（K6）
    assert not hasattr(outcome, "findings")


# ── 容错：坏行 / 空文件 / 二进制快照 / null entry / 未核对字段 ────────────


def test_parser_tolerates_bad_lines_and_empty_file(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        'not json\n{"type": "assistant", "message": {"role": "assistant"}}\n'
        '[1, 2]\n{"type": "assistant", "message": {"role": "assistant", "content": '
        '[{"type": "tool_use", "name": "Edit", "input": {"file_path": "/x.py"}}]}}\n',
        encoding="utf-8",
    )
    ir = parse_claude_session(bad)
    # 2 条坏行注记（逐行分立，消息含行号）+ 1 条 tool_use 事件成功提取
    assert sum(n.count for n in ir.notes if n.code == "bad_line") == 2
    assert len(ir.tool_events) == 1

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    ir = parse_claude_session(empty)
    assert ir.tool_events == () and ir.notes == ()


def test_claude_snapshot_null_entry_and_extra_fields(tmp_path):
    lines = [
        json.dumps(
            {
                "type": "file-history-snapshot",
                "snapshot": {
                    "trackedFileBackups": {
                        "/x.py": None,
                        "/y.py": {"backupFileName": "h@v1", "version": 1, "backupTime": "t", "realParentDir": "/"},
                        "/z.py": {"backupFileName": "h@v2", "version": 2, "backupTime": "t", "realParentDir": "/", "futureField": 1},
                    }
                },
            }
        )
    ]
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ir = parse_claude_session(p)
    codes = {n.code: n.count for n in ir.notes}
    assert codes.get("snapshot_entry_null") == 1
    assert codes.get("snapshot_entry_extra_field") == 1  # futureField 未核对 → 显式注记（K7）


def test_claude_multiedit_downgraded_with_note(tmp_path):
    """D-M1-4：MultiEdit 本机 0 次 → 出现时按 edit 降级 + ParseNote，不编造字段形态。"""
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "MultiEdit", "input": {"file_path": "/x.py"}}
                ],
            },
        }
    )
    p = tmp_path / "s.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    ir = parse_claude_session(p)
    assert [e.kind for e in ir.tool_events] == [KIND_EDIT]
    assert any(n.code == "multiedit_downgraded" for n in ir.notes)


def test_codex_unverified_payload_type_noted(tmp_path):
    line = json.dumps(
        {"type": "response_item", "payload": {"type": "reasoning", "summary": []}}
    )
    p = tmp_path / "s.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    ir = parse_codex_session(p)
    assert ir.tool_events == ()
    assert any(n.code == "unverified_payload_type_skipped" for n in ir.notes)


def test_codex_apply_patch_without_input_noted(tmp_path):
    line = json.dumps(
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch"}}
    )
    p = tmp_path / "s.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    ir = parse_codex_session(p)
    # 仍计一次写事件（R5 编辑计数主证据），路径 unknown + 显式注记
    assert len(ir.tool_events) == 1 and ir.tool_events[0].file_path is None
    assert any(n.code == "apply_patch_input_missing" for n in ir.notes)


def test_read_version_chains_missing_and_sparse(tmp_path):
    assert read_version_chains(tmp_path / "nonexistent") == {}
    # 目录存在但文件名不含 @vN → 证据不可用，链为空（不猜测）
    d = tmp_path / "fh" / "sess-1"
    d.mkdir(parents=True)
    (d / "abc.txt").write_bytes(b"data")
    (d / "def@v2.py").write_bytes(b"data")  # 带扩展名的 @vN 形态也可用
    chains = read_version_chains(tmp_path / "fh")
    assert chains["sess-1"]["def"]["versions"] == (2,)


def test_k7_unverified_fields_never_in_tool_events():
    """全样例扫描：解析器输出的 tool_events 只含核对过的 kind/tool_name 组合。"""
    verified_tool_names = {
        "Read", "Edit", "NotebookEdit", "Write", "MultiEdit", "Bash",  # Claude R4
        "exec", "apply_patch",  # Codex R3/R5
    }
    for case_dir in _iter_cases():
        loaded = _load_case(case_dir)
        if loaded is None:
            continue
        ir, _, _ = loaded
        for event in ir.tool_events:
            assert event.tool_name in verified_tool_names
            assert event.kind in ("read", "edit", "write", "exec", "other")
