"""报告层契约：披露制 / 零外链 / 确定性 / 空节不造假结论（★ K5/K6）。"""

from agent_rework_lens import __version__, config
from agent_rework_lens.engine.metrics import DupCandidate, SessionMetrics
from agent_rework_lens.engine.rework import ReworkFinding
from agent_rework_lens.report import render_html, render_markdown
from agent_rework_lens.report.model import DUP_DISCLOSURE, ReportMeta, ReportModel


def _meta() -> ReportMeta:
    return ReportMeta(
        title="演示报告（合成数据）",
        tool_name=config.TOOL_NAME,
        tool_version=__version__,
        source_summary="claude_sessions: 2 个文件",
        thresholds_note="见 config.py（单点定义）",
    )


def _model(with_rows: bool = True) -> ReportModel:
    if not with_rows:
        return ReportModel(meta=_meta())
    findings = (
        ReworkFinding(
            file_path="/demo/alpha/src/util_a.py",
            session_id="s-1",
            verdict="rework",
            version_count=3,
            edit_count=4,
            reasons=("versions>=N",),
            evidence=("s-1.jsonl:12", "a8f60eb1c3809243@v2"),
        ),
    )
    dup = (
        DupCandidate(
            new_symbol="format_value",
            existing_symbol="format_value_helper",
            match_reason="normalized_exact",
        ),
    )
    metrics = (SessionMetrics(session_id="s-1", reads=10, writes=3, read_edit_ratio=10 / 3),)
    return ReportModel(
        meta=_meta(), rework_findings=findings, dup_candidates=dup, session_metrics=metrics
    )


def test_markdown_contains_rows_and_disclosure():
    markdown = render_markdown(_model())
    assert "util_a.py" in markdown
    assert "format_value_helper" in markdown
    assert DUP_DISCLOSURE in markdown


def test_html_contains_rows_and_disclosure():
    html = render_html(_model())
    assert "util_a.py" in html
    assert DUP_DISCLOSURE in html


def test_html_zero_external_refs():
    html = render_html(_model()).lower()
    assert "http://" not in html
    assert "https://" not in html
    assert "<script" not in html
    assert "@import" not in html
    assert "url(" not in html


def test_render_deterministic_bytes():
    model = _model()
    assert render_markdown(model) == render_markdown(model)
    assert render_html(model) == render_html(model)


def test_empty_model_shows_no_data_not_fake_conclusion():
    markdown = render_markdown(_model(with_rows=False))
    html = render_html(_model(with_rows=False))
    assert "无数据（未启用或未发现达标文件）" in markdown
    assert "无数据（未启用或未发现达标文件）" in html


def test_ratio_undefined_renders_explicitly():
    model = ReportModel(
        meta=_meta(),
        session_metrics=(SessionMetrics(session_id="s-2", reads=5, writes=0, read_edit_ratio=None),),
    )
    assert "未定义（无写操作）" in render_markdown(model)
    assert "未定义（无写操作）" in render_html(model)


def test_markdown_escapes_pipe_in_cell():
    model = ReportModel(
        meta=_meta(),
        rework_findings=(
            ReworkFinding(file_path="a|b.py", session_id="s", verdict="rework"),
        ),
    )
    assert "a\\|b.py" in render_markdown(model)
