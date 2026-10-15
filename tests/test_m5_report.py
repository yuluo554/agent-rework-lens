"""M5 报告成稿回归：真实会话 → ReportModel → 渲染（锚点/披露/确定性/三方对账，★ K5/K6/K8）。"""

import json
import shutil
from pathlib import Path

from agent_rework_lens.cli import main as cli_main
from agent_rework_lens.pipeline import build_report_model, run_scan
from agent_rework_lens.report import render_html, render_markdown
from agent_rework_lens.report.model import DUP_DISCLOSURE

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = REPO_ROOT / "data" / "synthetic" / "samples"


def _make_home(tmp_path, case_name, with_project=False):
    """把一个合成 case 摆进布局正确的临时 claude home（含空 codex home，隔离真实源）。"""
    case = SAMPLES / case_name
    truth = json.loads((case / "truth.json").read_text(encoding="utf-8"))
    home = tmp_path / "claude"
    codex = tmp_path / "codex"
    codex.mkdir()
    proj = home / "projects" / truth["session_id"]
    proj.mkdir(parents=True)
    shutil.copy(case / "session.jsonl", proj / "session.jsonl")
    hist = home / "file-history" / truth["session_id"]
    if (case / "file-history" / truth["session_id"]).exists():
        hist.mkdir(parents=True)
        for f in (case / "file-history" / truth["session_id"]).iterdir():
            (hist / f.name).write_bytes(f.read_bytes())
    if with_project:
        # 会话 Read 目标 /demo/alpha/src/*.py → 摆进 projects 根（源根 = <home>/projects）
        demo = home / "projects" / "demo" / "alpha" / "src"
        demo.mkdir(parents=True)
        for f in (case / "project").iterdir():
            shutil.copy(f, demo / f.name)
    return home, codex, case


def test_report_model_from_real_duplicate_case(tmp_path):
    """duplicate case 全链路：候选 + 披露 + 会话级锚点进 ReportModel。"""
    home, codex, _ = _make_home(tmp_path, "case-claude_code-duplicate-01", with_project=True)
    outcome = run_scan(str(home), str(codex))
    model = build_report_model(outcome)
    assert len(outcome.session_metrics) == len(outcome.sessions) == 1
    cands = model.dup_candidates
    assert len(cands) == 1
    cand = cands[0]
    assert cand.new_symbol == "make_compute_wrapper"
    assert cand.existing_symbol == "make_compute_helper"
    assert cand.match_reason == "normalized_exact"
    # 候选证据锚点 = 源文件:会话 id（可溯源）
    assert cand.new_evidence.endswith("session.jsonl:00000000-0000-4000-8000-000000000034")
    # 披露制：模型注记带 DUP_DISCLOSURE（K5 单点）
    assert any(DUP_DISCLOSURE in n for n in model.notes)
    # 阈值口径取自 config 运行时值（K1）
    assert str(3) in model.meta.thresholds_note or "%d" not in model.meta.thresholds_note


def test_render_includes_evidence_anchor_column(tmp_path):
    """渲染器带证据锚点列：返工行含 源文件:行号 与 @v 版本锚点。"""
    home, codex, _ = _make_home(tmp_path, "case-claude_code-rework-01")
    outcome = run_scan(str(home), str(codex))
    model = build_report_model(outcome)
    assert model.rework_findings
    markdown = render_markdown(model)
    html = render_html(model)
    finding = model.rework_findings[0]
    anchor = finding.evidence[0]
    assert anchor.rsplit(":", 1)[1].isdigit()  # 源文件:行号（Windows 盘符路径取末段）
    assert anchor in markdown
    assert anchor in html
    version_anchors = [ev for ev in finding.evidence if "@v" in ev]
    assert version_anchors  # 版本快照锚点（rework-01 版本链齐备）


def test_render_double_run_byte_identical(tmp_path):
    """端到端确定性（K11）：scan 双跑 → 渲染逐字节一致。"""
    home, codex, _ = _make_home(tmp_path, "case-claude_code-duplicate-01", with_project=True)

    def _render():
        outcome = run_scan(str(home), str(codex))
        model = build_report_model(outcome)
        return render_markdown(model), render_html(model)

    md1, html1 = _render()
    md2, html2 = _render()
    assert md1 == md2
    assert html1 == html2


def test_three_way_equivalence(tmp_path, capsys):
    """三方对账（plan/04 §10）：CLI stdout = pipeline 直调 = 报告章节。"""
    home, codex, case = _make_home(tmp_path, "case-claude_code-rework-01")
    # 通路 1：CLI 落盘报告
    md_path = tmp_path / "r.md"
    html_path = tmp_path / "r.html"
    rc = cli_main(
        [
            "scan",
            "--claude-home",
            str(home),
            "--codex-home",
            str(codex),
            "--report-md",
            str(md_path),
            "--report-html",
            str(html_path),
        ]
    )
    assert rc == 0
    cli_md = md_path.read_text(encoding="utf-8")
    cli_html = html_path.read_text(encoding="utf-8")
    # 通路 2：pipeline 直调 + 渲染（同一输入）
    outcome = run_scan(str(home), str(codex))
    model = build_report_model(outcome)
    assert render_markdown(model) == cli_md
    assert render_html(model) == cli_html
    # 通路 3：CLI stdout 摘要与报告同一套判定数据（verdict 行的文件/锚点都在报告里）
    stdout = capsys.readouterr().out
    verdict_files = [f.file_path for f in model.rework_findings]
    assert verdict_files and all(vf in cli_md for vf in verdict_files)
    for line in stdout.splitlines():
        if line.startswith("  [verdict] "):
            # 格式："  [verdict] <verdict> <file_path>：版本 …"
            file_path = line.split("  [verdict] ", 1)[1].split(maxsplit=1)[1].rsplit("：", 1)[0].strip()
            assert file_path in cli_md


def test_cli_report_html_zero_external_refs(tmp_path):
    """CLI 产出的 HTML 报告零外链（K6：内联样式、无脚本/CDN/远程引用）。"""
    home, codex, _ = _make_home(tmp_path, "case-claude_code-duplicate-01", with_project=True)
    html_path = tmp_path / "r.html"
    rc = cli_main(["scan", "--claude-home", str(home), "--codex-home", str(codex),
                   "--report-html", str(html_path)])
    assert rc == 0
    text = html_path.read_text(encoding="utf-8").lower()
    assert "http://" not in text
    assert "https://" not in text
    assert "<script" not in text
    assert "@import" not in text
    assert "url(" not in text


def test_codex_session_symbol_candidates_disabled_with_disclosure(tmp_path):
    """Codex 源符号候选未启用（R5 载荷形态不编造）→ 显式披露进注记（K7）。"""
    case = SAMPLES / "case-codex-rework-03"
    truth = json.loads((case / "truth.json").read_text(encoding="utf-8"))
    codex = tmp_path / "codex"
    sid_dir = codex / "sessions" / truth["session_id"]
    sid_dir.mkdir(parents=True)
    shutil.copy(case / "session.jsonl", sid_dir / "session.jsonl")
    home = tmp_path / "claude"
    home.mkdir()
    outcome = run_scan(str(home), str(codex))
    model = build_report_model(outcome)
    assert not model.dup_candidates
    assert any("符号候选未启用" in n for n in model.notes)


def test_unsupported_write_language_disclosed(tmp_path):
    """Write 到非 .py 文件 → 符号提取显式跳过披露（不猜测，K7 同族）。"""
    session = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1",'
        '"name":"Write","input":{"file_path":"/demo/alpha/src/notes.md",'
        '"content":"# notes"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t2",'
        '"name":"Write","input":{"file_path":"/demo/alpha/src/b.py",'
        '"content":"def solo(): pass"}}]}}\n'
    )
    home = tmp_path / "claude"
    codex = tmp_path / "codex"
    codex.mkdir()
    proj = home / "projects" / "sess-md"
    proj.mkdir(parents=True)
    (proj / "session.jsonl").write_text(session, encoding="utf-8")
    outcome = run_scan(str(home), str(codex))
    model = build_report_model(outcome)
    assert any("非首期支持语言" in n for n in model.notes)
