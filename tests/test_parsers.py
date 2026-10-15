"""解析层：jsonl 容错读取 + 双源解析器（M2 起启用；护栏已按 K2 退役）。"""

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


def test_parsers_enabled_since_m2(tmp_path):
    """M2 起解析器启用；坏行只进 ParseNote 不抛异常（K2：护栏已退役）。"""
    path = tmp_path / "s.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    ir = parse_claude_session(str(path))
    assert ir.meta.source == "claude_code"
    ir = parse_codex_session(str(path))
    assert ir.meta.source == "codex"
