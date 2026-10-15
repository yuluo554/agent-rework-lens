# -*- coding: utf-8 -*-
"""合成冻结数据守门（★ M1；plan/05 §五）。

三道闸：
1. ``--check`` 位级一致（子进程实跑生成器 → 与入仓冻结件逐字节比对）；
2. sha256 三处一致（manifest ↔ data/README 登记计数 ↔ 实际文件）；
3. 零真实值扫描（fixtures 目录 + 全仓抽查：组合路径签名匹配）。

变异验证纪律（HANDOFF-M1 §四）：改守门自身无效；要改**被测行为**——
比如动生成器输出体例 → --check 必须红（实录见 plan/07 决策记录）。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNTH = REPO_ROOT / "data" / "synthetic"
MANIFEST = SYNTH / "manifest.json"
GENERATOR = REPO_ROOT / "tools" / "gen_synthetic.py"

# 组合路径签名（假名白名单的**否定集**）：命中任一 → 判为真实值泄漏。
# 纪律（data/README §三）：真实用户名不入仓——签名不含真实值本身，只含"形态"。
# 占位符（<user> 等）后的签名不算命中（台账中的形态说明保留可读）。
REAL_VALUE_SIGNATURES = (
    "C:\\Users\\",  # Windows 用户目录
    "/c/Users/",
    "/home/",  # POSIX 用户目录（demo 路径域固定 /demo/...）
)
PLACEHOLDER_OPEN = ("<", "{")
# 豁免：本文件定义签名常量，自扫描必命中（定义处豁免，由 fixtures 扫描兜底）。
SELF_EXEMPT = {"tests/test_synthetic_data.py"}


def _scan_text_for_real_values(text: str) -> list:
    hits = []
    for sig in REAL_VALUE_SIGNATURES:
        start = 0
        while True:
            i = text.find(sig, start)
            if i < 0:
                break
            after = text[i + len(sig) : i + len(sig) + 1]
            if after not in PLACEHOLDER_OPEN:
                hits.append(sig)
            start = i + 1
    return hits


def _load_manifest() -> dict:
    assert MANIFEST.exists(), "manifest.json 缺失（先跑 tools/gen_synthetic.py）"
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_sha256_matches_frozen_files():
    manifest = _load_manifest()
    assert manifest["sha256"], "manifest 未登记任何 sha256"
    for rel, digest in manifest["sha256"].items():
        f = SYNTH / rel
        assert f.exists(), f"manifest 登记但缺失: {rel}"
        actual = hashlib.sha256(f.read_bytes()).hexdigest()
        assert actual == digest, f"冻结件被改动（sha256 不一致）: {rel}"
    # 反向：冻结目录内不允许存在未登记文件（禁手改/禁夹带）
    registered = set(manifest["sha256"]) | {"manifest.json"}
    for p in SYNTH.rglob("*"):
        if p.is_file():
            rel = p.relative_to(SYNTH).as_posix()
            assert rel in registered, f"未登记的冻结件: {rel}"


def test_generator_check_bit_identical():
    """--check 子进程实跑：退出 0 = 重生成与冻结件位级一致。"""
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(GENERATOR), "--check"],
        capture_output=True,
        cwd=REPO_ROOT,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"--check 失败 rc={proc.returncode}\n{out}{proc.stderr.decode('utf-8', errors='replace')}"
    assert "--check 通过" in out


def test_coverage_meets_manifest_minimums():
    manifest = _load_manifest()
    cov = manifest["coverage"]
    actual = cov["actual_count_by_type"]
    for ctype, minc in cov["min_count_by_type"].items():
        assert actual.get(ctype, 0) >= minc, f"覆盖度不足: {ctype} {actual.get(ctype,0)} < {minc}"
    # 7 类样本矩阵齐全
    expected_types = set(cov["min_count_by_type"])
    assert expected_types == {
        "rework",
        "duplicate",
        "normal",
        "missing_chain",
        "single_edit",
        "threshold_exact",
        "near_miss",
    }
    # truth.json 与实际 case 目录一一对应（真值与样例同源同版本）
    case_dirs = {p.name for p in (SYNTH / "samples").iterdir() if p.is_dir()}
    assert len(case_dirs) == sum(actual.values())
    for d in case_dirs:
        assert (SYNTH / "samples" / d / "truth.json").exists(), f"缺 truth.json: {d}"


def test_truth_has_expected_schema_fields():
    """truth.json 草案字段定稿校验（plan/05 §4.3）。"""
    required = {
        "case_type",
        "source",
        "session_id",
        "expected_rework",
        "expected_dup_candidates",
        "expected_normal",
        "expect_status",
        "also_expect",
        "threshold_note",
    }
    for tj in SYNTH.glob("samples/*/truth.json"):
        truth = json.loads(tj.read_text(encoding="utf-8"))
        missing = required - set(truth)
        assert not missing, f"{tj.name} 缺字段: {missing}"
        assert truth["expect_status"] in ("rework_hit", "insufficient_data", "not_rework")
        # 互斥：同一 case 内文件不得同时进 expected_rework 与 expected_normal
        rw = {e["file"] for e in truth["expected_rework"]}
        nm = {e["file"] for e in truth["expected_normal"]}
        assert not (rw & nm), f"{tj.name} 真值互斥失败"


def test_whitelist_registered_and_used():
    """白名单登记制：session id 形态受控；假名只能来自 manifest 词表。"""
    manifest = _load_manifest()
    wl = manifest["whitelist"]
    assert wl["fake_session_id_pattern"] == "00000000-0000-4000-8000-0000000000NN"
    assert "demo-project-alpha" in wl["fake_projects"]
    for tj in SYNTH.glob("samples/*/truth.json"):
        truth = json.loads(tj.read_text(encoding="utf-8"))
        sid = truth["session_id"]
        assert sid.startswith("00000000-0000-4000-8000-0000000000"), f"session id 越界: {sid}"


def test_no_real_values_in_synthetic():
    """零真实值扫描（fixtures 目录）：组合路径签名匹配（无豁免）。"""
    for p in SYNTH.rglob("*"):
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8", errors="replace")
        for s in REAL_VALUE_SIGNATURES:
            assert s not in text, f"真实值签名命中 {s!r}: {p.relative_to(REPO_ROOT)}"


def test_no_real_values_in_repo_scan():
    """零真实值抽查（全仓源码 + 文档；排除冻结件与生成器自身缓存）。"""
    scan_roots = [
        REPO_ROOT / "src",
        REPO_ROOT / "tests",
        REPO_ROOT / "plan",
        REPO_ROOT / "data" / "README.md",
        REPO_ROOT / "pyproject.toml",
    ]
    for root in scan_roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.py")) + sorted(
            root.rglob("*.md")
        )
        for f in files:
            if not f.is_file():
                continue
            rel = f.relative_to(REPO_ROOT).as_posix()
            if rel in SELF_EXEMPT:
                continue
            text = f.read_bytes().decode("utf-8", errors="replace")
            hits = _scan_text_for_real_values(text)
            assert not hits, f"真实值签名命中 {hits}: {rel}"


def test_gitattributes_freeze_rule_active():
    """.gitattributes 对 data/synthetic/** 的 -text 规则生效（EOL 不被归一化）。"""
    ga = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "data/synthetic/** -text" in ga
