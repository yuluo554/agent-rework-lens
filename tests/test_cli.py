"""CLI 退出码契约（★ K2）与双通路（★ K8）。

进程内（capsys）覆盖全部分支；子进程真实通路覆盖 `python -m` 与裸 `arl`。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agent_rework_lens import __version__, config
from agent_rework_lens.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"


def _run_cli(args):
    """子进程真实通路。子进程 stdout 编码依赖 locale → 显式 utf-8（教训族纪律）。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "agent_rework_lens"] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(REPO_ROOT),
    )


def _claude_tree(tmp_path):
    claude = tmp_path / "claude"
    (claude / "projects" / "p").mkdir(parents=True)
    (claude / "projects" / "p" / "s.jsonl").write_text("{}\n", encoding="utf-8")
    return claude


# ── 进程内分支 ────────────────────────────────────────────────────────────


def test_version_command(capsys):
    rc = main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert config.TOOL_NAME in out
    assert __version__ in out


def test_top_level_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_lists_subcommands(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for command in ("version", "sources", "scan", "selftest"):
        assert command in out


def test_unknown_command_exit_2(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["definitely-not-a-command"])
    assert excinfo.value.code == 2


def test_no_subcommand_exit_2():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_sources_no_source_exit_0_with_honest_message(tmp_path, capsys):
    rc = main(["sources", "--claude-home", str(tmp_path / "a"), "--codex-home", str(tmp_path / "b")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "未发现可分析日志源" in out


def test_sources_found_lists_counts(tmp_path, capsys):
    claude = _claude_tree(tmp_path)
    rc = main(["sources", "--claude-home", str(claude), "--codex-home", str(tmp_path / "nonexistent"), "--source", "claude"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "claude_sessions" in out
    assert "1 个文件" in out


def test_sources_json_machine_readable(tmp_path, capsys):
    claude = _claude_tree(tmp_path)
    rc = main(["sources", "--claude-home", str(claude), "--codex-home", str(tmp_path / "nonexistent"), "--source", "claude", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["command"] == "sources"
    assert payload["total_files"] == 1
    assert payload["locations"][0]["kind"] == "claude_sessions"


def test_scan_no_sources_exit_3(tmp_path, capsys):
    rc = main(["scan", "--claude-home", str(tmp_path / "a"), "--codex-home", str(tmp_path / "b")])
    captured = capsys.readouterr()
    assert rc == 3
    assert "未发现可分析日志源" in captured.err


def test_scan_parses_and_prints_summary_exit_0(tmp_path, capsys):
    """M2 起 scan 完成"发现→解析→IR"并以退出码 0 输出摘要（K2：4 已退役）。"""
    claude = _claude_tree(tmp_path)
    rc = main(["scan", "--claude-home", str(claude), "--codex-home", str(tmp_path / "nonexistent")])
    captured = capsys.readouterr()
    assert rc == 0
    assert "scan 完成" in captured.out
    assert "1 个会话" in captured.out


def test_selftest_ok(capsys):
    rc = main(["selftest"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[ok]" in out


def test_selftest_json(capsys):
    rc = main(["selftest", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["checks"]


# ── 子进程真实通路（系统 Python 独立进程） ─────────────────────────────────


def test_subprocess_module_entry_version():
    result = _run_cli(["version"])
    assert result.returncode == 0
    assert __version__ in result.stdout


def test_subprocess_module_entry_no_sources_exit_3(tmp_path):
    result = _run_cli(["scan", "--claude-home", str(tmp_path / "a"), "--codex-home", str(tmp_path / "b")])
    assert result.returncode == 3
    assert "未发现可分析日志源" in result.stderr


def test_console_script_bare_command():
    arl = shutil.which("arl")
    if arl is None:
        pytest.skip("未安装控制台脚本（源码态运行）；安装态与 CI 覆盖本通路")
    result = subprocess.run(
        [arl, "version"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
