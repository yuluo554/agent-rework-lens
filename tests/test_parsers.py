"""解析层：jsonl 容错读取 + 骨架护栏。"""

import pytest

from agent_rework_lens.errors import StageNotReady
from agent_rework_lens.parsers import parse_claude_session, parse_codex_session
from agent_rework_lens.parsers.common import iter_jsonl_lines


def test_iter_jsonl_lines_reports_bad_lines_not_silent(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text(
        '{"a": 1}\n'
        "\n"
        "not json\n"
        "[1, 2]\n"
        '{"b": 2}\n',
        encoding="utf-8",
    )
    results = list(iter_jsonl_lines(path))
    assert results[0] == (1, {"a": 1}, None)
    assert results[1][0] == 3 and results[1][1] is None and "malformed" in results[1][2]
    assert results[2] == (4, None, "non_object_json_line")
    assert results[3] == (5, {"b": 2}, None)


def test_iter_jsonl_lines_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert list(iter_jsonl_lines(path)) == []


def test_parsers_stage_guard_until_m2(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(StageNotReady) as claude_exc:
        parse_claude_session(str(path))
    assert "M2" in str(claude_exc.value)
    with pytest.raises(StageNotReady) as codex_exc:
        parse_codex_session(str(path))
    assert "M2" in str(codex_exc.value)
