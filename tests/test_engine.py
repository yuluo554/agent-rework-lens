"""引擎层：已实现算法单元测试（M3）。truth 驱动逐例对账见 tests/test_m3_engine.py。"""

import pytest

from agent_rework_lens.engine import metrics, rework, symbols
from agent_rework_lens.engine.metrics import (
    DUP_DISCLOSURE,
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
    """未支持语言仍走显式拒绝路径（K7 同族纪律）；其余护栏随 M3 实现退役。"""
    assert symbols.extract_defined_symbols("def f():\n    pass\n", "javascript") is None
    assert symbols.is_supported_language("javascript") is False
    assert symbols.is_supported_language("python") is True


def test_symbol_extraction_python():
    text = (
        "import os\n"
        "def top_fn(value):\n"
        "    return value\n"
        "class TopClass:\n"
        "    async def inner_method(self):\n"
        "        pass\n"
        "    def _private_fn(self):\n"
        "        pass\n"
    )
    result = symbols.extract_defined_symbols(text, "python")
    assert result is not None
    names = [(s.name, s.kind, s.line_in_payload) for s in result]
    assert names == [
        ("top_fn", "function", 2),
        ("TopClass", "class", 4),
        ("inner_method", "function", 5),
        ("_private_fn", "function", 7),
    ]


def test_symbol_extraction_empty_and_bad_input():
    assert symbols.extract_defined_symbols("x = 1\n", "python") == ()
    # 非 Python 文本传入 Python 提取 → 空 tuple（提取不到，不冒充"没有符号"之外的含义）
    assert symbols.extract_defined_symbols("def fake_not_python", "python") == ()


def test_normalize_symbol_name_frozen_steps():
    # plan/04 §7.4：小写 / - → _ / 去首尾 _ / 首 token 前缀词表 + 尾 token 后缀词表（可迭代）/ 拼接
    assert metrics.normalize_symbol_name("Make_Compute-Wrapper") == "compute"
    assert metrics.normalize_symbol_name("compute_helper") == "compute"
    assert metrics.normalize_symbol_name("get_fetch_compute") == "compute"
    assert metrics.normalize_symbol_name("compute") == "compute"
    # 词表只剔首/尾 token：中段词与另一端不合词表的词保留
    assert metrics.normalize_symbol_name("helper_compute") == "helpercompute"


def test_match_symbols_two_levels():
    reason, similarity = metrics.match_symbols("make_compute_wrapper", "make_compute_helper")
    assert reason == "normalized_exact"
    assert similarity is None
    reason, similarity = metrics.match_symbols("fetch_data_impl", "get_data_fn")
    # 归一化后同为 data → 精确相等命中
    assert reason == "normalized_exact"
    assert similarity is None
    # 相似度低于阈值 → None
    assert metrics.match_symbols("totally_different", "xyz") is None


def test_find_dup_candidates_deterministic_and_k5_disclosure():
    new = symbols.extract_defined_symbols("def make_compute_wrapper(v):\n    return v\n")
    existing = symbols.extract_defined_symbols(
        "def make_compute_helper(v):\n    return v\n\nclass Unrelated:\n    pass\n"
    )
    candidates = metrics.find_dup_candidates(new, existing, "sess.jsonl:4", "project/common.py:1")
    assert len(candidates) == 1
    cand = candidates[0]
    assert (cand.new_symbol, cand.existing_symbol, cand.match_reason) == (
        "make_compute_wrapper",
        "make_compute_helper",
        "normalized_exact",
    )
    assert cand.new_evidence == "sess.jsonl:4"
    assert cand.existing_evidence == "project/common.py:1"
    # 双跑一致
    assert metrics.find_dup_candidates(new, existing, "sess.jsonl:4", "project/common.py:1") == candidates
    # K5：披露文本单点存在且非空
    assert DUP_DISCLOSURE and "粗匹配" in DUP_DISCLOSURE


def test_compute_session_metrics_aggregates():
    events = (
        ToolUseEvent(seq=1, kind="read", tool_name="Read"),
        ToolUseEvent(seq=2, kind="read", tool_name="Read"),
        ToolUseEvent(seq=3, kind="edit", tool_name="Edit"),
        ToolUseEvent(seq=4, kind="write", tool_name="Write"),
        ToolUseEvent(seq=5, kind="exec", tool_name="Bash"),
    )
    m = metrics.compute_session_metrics("s1", events)
    assert (m.reads, m.writes) == (2, 2)
    assert m.read_edit_ratio == 1.0
    assert m.writes_by_kind == (("edit", 1), ("write", 1))
    assert m.dup_candidates == ()


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
