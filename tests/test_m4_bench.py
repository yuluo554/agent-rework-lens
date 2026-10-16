"""M4 基准回归（plan/06 M4 DoD）。

覆盖：truth 全量对账（复现）、退出码三语义（0/1/2）、"未启用"不冒充通过、
覆盖率门槛拦截、探活变异验证（注入缺陷 → 必须报未达标）、双跑确定性。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agent_rework_lens import config
from agent_rework_lens.benchmark.runner import run_bench
from agent_rework_lens.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "synthetic"


# ── 管线级：run_bench 全量对账 ────────────────────────────────────────────


def test_bench_all_cases_match_truth():
    result = run_bench(DATA_DIR)
    assert not result.not_enabled
    assert result.case_count == 12
    assert result.rework_total == 4
    assert result.rework_hit == result.rework_total
    assert result.false_positive == 0
    assert result.not_rework_total == 7
    assert result.anchor_ok == result.anchor_total
    assert result.anchor_total > 0
    assert result.passed, result.failures()
    assert result.failures() == []


def test_bench_double_run_identical():
    """确定性（K11）：同一数据两次评测逐字段一致。"""
    assert repr(run_bench(DATA_DIR)) == repr(run_bench(DATA_DIR))


def test_bench_coverage_thresholds_only_from_manifest():
    """门槛数值只来自 manifest（代码零数值）：required 必须与 manifest 逐项相等。"""
    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    result = run_bench(DATA_DIR)
    assert result.coverage.required == manifest["coverage"]["min_count_by_type"]
    assert result.coverage.actual == manifest["coverage"]["actual_count_by_type"]


def test_bench_not_enabled_does_not_pass(tmp_path):
    """"未启用"套件不冒充通过：空分母 → not_enabled + 说明 + not passed。"""
    result = run_bench(tmp_path / "does-not-exist")
    assert result.not_enabled
    assert not result.passed
    assert "未启用" in result.not_enabled_detail
    assert result.failures()


def test_bench_not_enabled_empty_dir(tmp_path):
    """空目录（有目录无样例）同样按未启用拦截。"""
    result = run_bench(tmp_path)
    assert result.not_enabled
    assert not result.passed


# ── 覆盖率门槛拦截（不达标演示的可复用机制） ──────────────────────────────


@pytest.fixture
def bench_copy(tmp_path):
    """拷贝一份数据目录供变异（fixtures 冻结件禁手改，K9：变异只动副本）。"""
    target = tmp_path / "synthetic"
    shutil.copytree(DATA_DIR, target)
    return target


def _case_types_in_copies(bench_dir: Path):
    samples = bench_dir / "samples"
    return [p.name for p in sorted(samples.iterdir()) if p.is_dir()]


def test_bench_fails_when_case_removed_below_threshold(bench_copy):
    """删一个 rework 样例 → 实际 2 < 门槛 2？不，剩 2 恰好达标；
    删两个 → 门槛不足 → 明确拦截（对应 plan/06"不达标演示"）。"""
    for name in ("case-claude_code-rework-01", "case-claude_code-rework-02"):
        shutil.rmtree(bench_copy / "samples" / name)
    result = run_bench(bench_copy)
    assert not result.passed
    failures = result.failures()
    assert any("覆盖率" in f and "rework" in f for f in failures), failures


def test_bench_fails_when_manifest_requires_more(bench_copy):
    """改副本 manifest（把 normal 门槛提到 99）→ 门槛不足 → 拦截。"""
    manifest_path = bench_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["coverage"]["min_count_by_type"]["normal"] = 99
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result = run_bench(bench_copy)
    assert not result.passed
    assert any("normal" in f and "99" in f for f in result.failures())


def test_bench_fails_when_truth_missing_chain_breaks(bench_copy):
    """篡改副本 truth（normal-01 谎报 rework）→ 引擎与真值对不上 → 该样例 FAIL。"""
    truth_path = bench_copy / "samples" / "case-claude_code-normal-01" / "truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["case_type"] = "rework"  # 谎报类型，expected_verdict 随之变 rework
    truth_path.write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result = run_bench(bench_copy)
    assert not result.passed
    failed = [c for c in result.cases if not c.ok]
    assert any("normal-01" in c.case_id for c in failed)


def test_bench_fails_when_fixture_hash_mismatch(bench_copy):
    """副本冻结件被改（session.jsonl 尾部追加空行）→ sha256 对账失败 → 拦截。"""
    session = bench_copy / "samples" / "case-claude_code-rework-01" / "session.jsonl"
    session.write_bytes(session.read_bytes() + b"\n")
    result = run_bench(bench_copy)
    assert not result.passed
    assert any("sha256" in f for f in result.failures())


# ── 探活变异验证（可证伪）：注入缺陷 → 基准必须报未达标 ──────────────────


def test_mutation_forced_rework_false_kills_bench(bench_copy, monkeypatch):
    """探活 A：把返工判定强行置 False（引擎返回空 findings）→ rework 4 例全灭
    → 覆盖率 + 判定双失败。恢复（monkeypatch 自动还原）→ 基准变绿。"""
    from agent_rework_lens.benchmark import runner as runner_mod

    monkeypatch.setattr(runner_mod, "analyze_rework", lambda *a, **k: ())
    result = run_bench(bench_copy)
    assert not result.passed
    failures = result.failures()
    assert any("rework-01" in f for f in failures), failures
    # 恢复（解除注入）后变绿（同一副本，无注入）
    monkeypatch.undo()
    assert run_bench(bench_copy).passed


def test_mutation_threshold_shift_kills_bench(bench_copy, monkeypatch):
    """探活 B：把 M 阈值抬到 99 → threshold_exact/codex 依赖 edits 的命中塌掉
    → 基准必须报未达标。"""
    monkeypatch.setattr(config, "REWORK_MIN_EDITS", 99)
    result = run_bench(bench_copy)
    assert not result.passed
    assert any("codex-rework-03" in f for f in result.failures()), result.failures()


def test_mutation_high_similarity_branch_kills_bench(bench_copy, monkeypatch):
    """探活 D（粗匹配第二级）：把高相似阈值抬到 1.0 → duplicate-03 的
    high_similarity 分支塌掉（归一化不等且 ratio < 1.0）→ 基准必须报未达标；
    同时确认该分支确被 bench 对账覆盖（duplicate-03 报符号候选失败）。
    """
    original = config.DUP_MATCH_THRESHOLD
    monkeypatch.setattr(config, "DUP_MATCH_THRESHOLD", 1.0)
    result = run_bench(bench_copy)
    assert not result.passed
    failures = result.failures()
    assert any("duplicate-03" in f for f in failures), failures
    # 恢复阈值 → 同一副本变绿（证明红来自该分支，而非其它偶发）
    monkeypatch.setattr(config, "DUP_MATCH_THRESHOLD", original)
    assert run_bench(bench_copy).passed


def test_mutation_via_subprocess_recovered_green(bench_copy, tmp_path):
    """探活 C（真实通路）：写一个 sitecustomize 式的缺陷补丁文件，用
    PYTHONSTARTUP 不可行（交互才生效）→ 改用子进程 + -c 注入 patch 后调 main。
    验证注入 → 退出码 1；去掉注入 → 退出码 0。"""
    from agent_rework_lens import engine as engine_pkg
    from agent_rework_lens.engine import rework as rework_mod

    injected_source = (
        "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "from agent_rework_lens.engine import rework as m\n"
        "m.analyze_rework = lambda *a, **k: ()\n"
        "from agent_rework_lens.cli import main\n"
        "sys.exit(main(['bench', '--data-dir', %r]))\n"
        % (str(REPO_ROOT / "src"), str(tmp_path), str(bench_copy))
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", injected_source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "未达标" in proc.stdout

    # 去掉注入 → 同一数据变绿（退出码 0）
    clean_source = (
        "import sys; sys.path.insert(0, %r)\n"
        "from agent_rework_lens.cli import main\n"
        "sys.exit(main(['bench', '--data-dir', %r]))\n"
        % (str(REPO_ROOT / "src"), str(bench_copy))
    )
    proc_clean = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", clean_source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc_clean.returncode == 0, proc_clean.stdout + proc_clean.stderr


# ── CLI 层：退出码三语义 + 输出 ───────────────────────────────────────────


def test_cli_bench_ok_exit_zero(capsys):
    assert main(["bench", "--data-dir", str(DATA_DIR)]) == 0
    out = capsys.readouterr().out
    assert "达标" in out
    assert "12 样例" in out


def test_cli_bench_not_enabled_exit_one(capsys, tmp_path):
    assert main(["bench", "--data-dir", str(tmp_path / "missing")]) == 1
    out = capsys.readouterr().out
    assert "未启用" in out
    assert "不冒充" in out


def test_cli_bench_not_meet_exit_one(capsys, bench_copy):
    """覆盖率门槛不足 → CLI 退出码 1 + 未达标清单。"""
    manifest_path = bench_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["coverage"]["min_count_by_type"]["rework"] = 99
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    assert main(["bench", "--data-dir", str(bench_copy)]) == 1
    out = capsys.readouterr().out
    assert "未达标" in out


def test_cli_bench_usage_error_exit_two(capsys):
    """坏参数（未知选项）→ 退出码 2（argparse 用法语义）。"""
    with pytest.raises(SystemExit) as excinfo:
        main(["bench", "--no-such-option"])
    assert excinfo.value.code == 2


def test_cli_bench_json_deterministic(capsys):
    assert main(["bench", "--data-dir", str(DATA_DIR), "--json"]) == 0
    first = capsys.readouterr().out
    assert main(["bench", "--data-dir", str(DATA_DIR), "--json"]) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert payload["command"] == "bench"
    assert payload["passed"] is True
    assert payload["summary"]["case_count"] == 12
    # 机读 JSON 同样携带门槛来源对账（K1：数值只在下发数据）
    assert payload["coverage"]["required"]["rework"] == 2


def test_cli_bench_json_not_enabled(capsys, tmp_path):
    assert main(["bench", "--data-dir", str(tmp_path), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["not_enabled"] is True
    assert payload["passed"] is False
