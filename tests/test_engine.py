"""引擎层：已实现的口径助手 + 未就绪护栏（类型冻结）。"""

import pytest

from agent_rework_lens.engine import metrics, rework, symbols
from agent_rework_lens.engine.metrics import (
    DupCandidate,
    SessionMetrics,
    compute_read_edit_ratio,
    count_read_write,
)
from agent_rework_lens.errors import StageNotReady
from agent_rework_lens.ir import ToolUseEvent


def test_count_read_write_uses_config_sets():
    events = (
        ToolUseEvent(seq=1, kind="read", tool_name="Read"),
        ToolUseEvent(seq=2, kind="read", tool_name="Read"),
        ToolUseEvent(seq=3, kind="edit", tool_name="Edit"),
        ToolUseEvent(seq=4, kind="write", tool_name="Write"),
        ToolUseEvent(seq=5, kind="exec", tool_name="Bash"),
        ToolUseEvent(seq=6, kind="other", tool_name="TaskCreate"),
    )
    assert count_read_write(events) == (2, 2)  # exec / other 不计入任何分子分母


def test_ratio_undefined_when_no_writes():
    assert compute_read_edit_ratio(5, 0) is None
    assert compute_read_edit_ratio(0, 0) is None


def test_ratio_defined_value():
    assert compute_read_edit_ratio(10, 4) == 2.5


def test_stage_guards_raise_with_plan_hint():
    with pytest.raises(StageNotReady) as excinfo:
        rework.analyze_rework()
    assert "M3" in str(excinfo.value)

    with pytest.raises(StageNotReady):
        metrics.find_dup_candidates()

    with pytest.raises(StageNotReady):
        symbols.extract_defined_symbols("def f():\n    pass\n")


def test_types_constructible_with_defaults():
    finding = rework.ReworkFinding(file_path="x.py", session_id="s", verdict=rework.VERDICT_INSUFFICIENT)
    assert finding.version_count is None  # 链缺失不猜测
    assert finding.edit_count == 0

    cand = DupCandidate(new_symbol="a", existing_symbol="b", match_reason="normalized_exact")
    assert cand.similarity is None

    session = SessionMetrics(session_id="s")
    assert session.read_edit_ratio is None


def test_verdict_registry_locked():
    assert rework.VERDICTS == ("rework", "not_rework", "insufficient_data")
