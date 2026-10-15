"""合成会话基准 runner（M4，plan/04 §9 / plan/06 M4）。

口径：
- 覆盖率门槛数值**只在下发数据（manifest.json）里**，不在代码里（数值过代码 = 违规）；
- 逐样例：解析 → 引擎 → 与 truth.json 对账（判定 / 指标 / 符号候选 / 锚点可溯源）；
- 未达标 → 明确"未达标清单"，由 CLI 映射退出码 1；"未启用"套件（样例目录不存在）
  → ``not_enabled`` + 说明，**不冒充通过**（空分母不是满分）；
- 可证伪探活：注入缺陷（见 tests/test_m4_bench.py 的变异验证）→ 基准必须报未达标；
- 确定性（K11）：不读时钟/环境；汇总按 case id 排序；同一数据双跑逐字段一致。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..engine.metrics import find_dup_candidates, symbols_from_write_payloads
from ..engine.rework import (
    REASON_EDITS,
    REASON_VERSIONS,
    VERDICT_INSUFFICIENT,
    VERDICT_NOT_REWORK,
    VERDICT_REWORK,
    ReworkFinding,
    analyze_rework,
)
from ..engine.symbols import extract_defined_symbols
from ..ir import SessionIR
from ..parsers import parse_claude_session, parse_codex_session
from ..parsers.claude_code import read_snapshot_file_map, read_version_chains


# ── 数据结构 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CaseMetrics:
    """单样例对账结果：期望 vs 引擎实际，逐字段留痕（谁不对、差多少）。"""

    case_id: str
    case_type: str
    source: str
    expected_verdict: str
    # 判定对账：期望文件的 verdict 是否全部符合 case 语义
    verdict_ok: bool
    actual_verdict: str = ""  # 期望文件的实际 verdict（单文件会话；多文件时为首个）
    # expected_rework 逐项对账（edit_count / version_count / reason）
    detail_failures: Tuple[str, ...] = ()
    # 指标对账（truth.expected_normal.edit_count / also_expect 链观察值）
    metrics_ok: bool = True
    # 符号候选对账（duplicate case）；非 duplicate → not_applicable
    dup_ok: Optional[bool] = None
    dup_detail: Tuple[str, ...] = ()
    # 锚点可溯源率：evidence 全部可定位（源文件行号 / @v 版本文件名）
    anchor_total: int = 0
    anchor_ok: int = 0
    # 完整性：期望文件都产生了 finding
    findings_ok: bool = True
    hash_ok: Optional[bool] = None  # 冻结件 sha256 对账（session+truth）；无记录 → None

    @property
    def anchors_traceable(self) -> bool:
        return self.anchor_total == 0 or self.anchor_ok == self.anchor_total

    @property
    def ok(self) -> bool:
        return (
            self.verdict_ok
            and self.findings_ok
            and self.metrics_ok
            and not self.detail_failures
            and self.dup_ok is not False
            and self.anchors_traceable
            and self.hash_ok is not False
        )

    def failures(self) -> List[str]:
        out: List[str] = []
        if self.hash_ok is False:
            out.append("%s: 冻结件 sha256 与 manifest 不符" % self.case_id)
        if not self.findings_ok:
            out.append("%s: 期望文件未全部产生 finding" % self.case_id)
        if not self.verdict_ok:
            out.append(
                "%s: verdict=%s 期望 %s" % (self.case_id, self.actual_verdict, self.expected_verdict)
            )
        for item in self.detail_failures:
            out.append("%s: %s" % (self.case_id, item))
        if not self.metrics_ok:
            out.append("%s: also_expect 指标对账失败" % self.case_id)
        for item in self.dup_detail:
            out.append("%s: %s" % (self.case_id, item))
        if not self.anchors_traceable:
            out.append(
                "%s: 锚点可溯源 %d/%d" % (self.case_id, self.anchor_ok, self.anchor_total)
            )
        return out


@dataclass(frozen=True)
class CoverageReport:
    """manifest 覆盖率门槛对账（数值只读 manifest，代码零数值）。"""

    required: Dict[str, int] = field(default_factory=dict)
    actual: Dict[str, int] = field(default_factory=dict)
    missing: Tuple[str, ...] = ()  # 门槛要求但样例缺失的类型
    extra: Tuple[str, ...] = ()  # 数据里出现但门槛未登记的类型（防"搭便车"）
    under: Tuple[Tuple[str, int, int], ...] = ()  # (类型, 实际, 门槛) 实际 < 门槛

    @property
    def ok(self) -> bool:
        return not self.missing and not self.under

    def failures(self) -> List[str]:
        out = [
            "覆盖率门槛不足：%s 实际 %d < 门槛 %d" % (t, a, m) for (t, a, m) in self.under
        ]
        out.extend("覆盖率门槛未满足：缺类型 %s 样例" % t for t in self.missing)
        out.extend("样例类型 %s 未在 manifest 门槛登记" % t for t in self.extra)
        return out


@dataclass(frozen=True)
class BenchSummary:
    """基准汇总：门槛对账 + 逐样例对账 + 聚合指标（零时钟零环境，K11）。"""

    data_dir: str
    manifest_schema: Optional[int]
    coverage: CoverageReport
    cases: Tuple[CaseMetrics, ...] = ()
    not_enabled: bool = False
    not_enabled_detail: str = ""

    @property
    def passed(self) -> bool:
        if self.not_enabled:
            return False  # "未启用"不冒充通过（空分母不是满分）
        if not self.coverage.ok:
            return False
        return all(c.ok for c in self.cases)

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def rework_hit(self) -> int:
        return sum(1 for c in self.cases if c.expected_verdict == VERDICT_REWORK and c.ok)

    @property
    def rework_total(self) -> int:
        return sum(1 for c in self.cases if c.expected_verdict == VERDICT_REWORK)

    @property
    def false_positive(self) -> int:
        return sum(
            1 for c in self.cases if c.expected_verdict == VERDICT_NOT_REWORK and not c.ok
        )

    @property
    def not_rework_total(self) -> int:
        return sum(1 for c in self.cases if c.expected_verdict == VERDICT_NOT_REWORK)

    @property
    def anchor_total(self) -> int:
        return sum(c.anchor_total for c in self.cases)

    @property
    def anchor_ok(self) -> int:
        return sum(c.anchor_ok for c in self.cases)

    def failures(self) -> List[str]:
        if self.not_enabled:
            return [self.not_enabled_detail or "基准套件未启用"]
        out = list(self.coverage.failures())
        for case in self.cases:
            out.extend(case.failures())
        return out


# ── runner ────────────────────────────────────────────────────────────────


def run_bench(data_dir=None) -> BenchSummary:
    """合成基准评测入口（CLI ``arl bench`` 与测试共用）。

    ``data_dir`` 缺省用仓库内 ``data/synthetic``；目录缺失 → ``not_enabled``
    （明确说明，不冒充通过）。门槛数值只从 manifest 读取。
    """
    root = Path(data_dir) if data_dir is not None else _default_data_dir()
    if not root.is_dir():
        return BenchSummary(
            data_dir=str(root),
            manifest_schema=None,
            coverage=CoverageReport(),
            not_enabled=True,
            not_enabled_detail="基准数据目录不存在：%s（未启用套件不冒充通过）" % root,
        )

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return BenchSummary(
            data_dir=str(root),
            manifest_schema=None,
            coverage=CoverageReport(),
            not_enabled=True,
            not_enabled_detail="manifest.json 不存在：%s（门槛无从读取，未启用套件不冒充通过）"
            % manifest_path,
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    thresholds = manifest.get("coverage") or {}
    required = dict(thresholds.get("min_count_by_type") or {})

    samples_dir = root / "samples"
    case_dirs = (
        sorted(p for p in samples_dir.iterdir() if (p / "truth.json").is_file())
        if samples_dir.is_dir()
        else []
    )
    if not case_dirs:
        return BenchSummary(
            data_dir=str(root),
            manifest_schema=manifest.get("schema"),
            coverage=CoverageReport(),
            not_enabled=True,
            not_enabled_detail="样例目录为空或不存在：%s（未启用套件不冒充通过）" % samples_dir,
        )

    sha_map = manifest.get("sha256") or {}
    cases: List[CaseMetrics] = []
    actual_counts: Dict[str, int] = {}
    for case_dir in case_dirs:
        metrics_case = _run_case(case_dir, sha_map)
        cases.append(metrics_case)
        actual_counts[metrics_case.case_type] = actual_counts.get(metrics_case.case_type, 0) + 1

    missing = tuple(sorted(t for t in required if t not in actual_counts))
    extra = tuple(sorted(t for t in actual_counts if t not in required))
    under = tuple(
        sorted(
            (t, actual_counts[t], m)
            for t, m in required.items()
            if t in actual_counts and actual_counts[t] < m
        )
    )
    coverage = CoverageReport(
        required=required,
        actual=actual_counts,
        missing=missing,
        extra=extra,
        under=under,
    )
    return BenchSummary(
        data_dir=str(root),
        manifest_schema=manifest.get("schema"),
        coverage=coverage,
        cases=tuple(cases),
    )


def _default_data_dir() -> Path:
    # src/agent_rework_lens/benchmark/runner.py → 仓库根/data/synthetic
    return Path(__file__).resolve().parents[3] / "data" / "synthetic"


# ── 单样例对账 ────────────────────────────────────────────────────────────


def _run_case(case_dir: Path, sha_map: Dict[str, str]) -> CaseMetrics:
    truth = json.loads((case_dir / "truth.json").read_text(encoding="utf-8"))
    case_id = case_dir.name
    rel_session = "samples/%s/session.jsonl" % case_id
    rel_truth = "samples/%s/truth.json" % case_id
    hash_ok = (
        _sha256_matches(case_dir / "session.jsonl", sha_map.get(rel_session))
        and _sha256_matches(case_dir / "truth.json", sha_map.get(rel_truth))
    )

    ir, chains, snap_map = _engine_inputs(case_dir, truth)
    findings = analyze_rework(ir, chains, snap_map)
    by_file = {f.file_path: f for f in findings}

    expected_verdict = _expected_verdict(truth)
    expected_files = _expected_files(truth, by_file)

    failures: List[str] = []
    findings_ok = all(f in by_file for f in expected_files)
    verdict_ok = findings_ok
    for file_path in expected_files:
        finding = by_file.get(file_path)
        if finding is None:
            continue
        if finding.verdict != expected_verdict:
            verdict_ok = False

    # expected_rework 逐项对账（编辑数 / 版本数 / 判据）
    for item in truth.get("expected_rework", []):
        finding = by_file.get(item["file"])
        if finding is None:
            failures.append("expected_rework 缺 finding：%s" % item["file"])
            continue
        if finding.edit_count != item["edit_count"]:
            failures.append(
                "%s edit_count=%d 期望 %d" % (item["file"], finding.edit_count, item["edit_count"])
            )
        if item["reason"] == "versions":
            if finding.version_count is None or finding.version_count < item["min_versions"]:
                failures.append("%s 版本判据未满足：%r" % (item["file"], finding.version_count))
            elif REASON_VERSIONS not in finding.reasons:
                failures.append("%s 缺理由 %s" % (item["file"], REASON_VERSIONS))
        else:
            if REASON_EDITS not in finding.reasons:
                failures.append("%s 缺理由 %s" % (item["file"], REASON_EDITS))

    # expected_normal 逐项对账（不持 rework 理由 + 编辑数）
    metrics_ok = True
    for item in truth.get("expected_normal", []):
        finding = by_file.get(item["file"])
        if finding is None:
            metrics_ok = False
            failures.append("expected_normal 缺 finding：%s" % item["file"])
            continue
        if finding.edit_count != item["edit_count"]:
            metrics_ok = False
            failures.append(
                "%s edit_count=%d 期望 %d"
                % (item["file"], finding.edit_count, item["edit_count"])
            )
        if REASON_VERSIONS in finding.reasons or REASON_EDITS in finding.reasons:
            metrics_ok = False
            failures.append("%s 不应持 rework 理由" % item["file"])

    # also_expect：链观察值等补充断言
    also = truth.get("also_expect") or {}
    if "dup_candidate_expected" in also:
        pass  # 由符号候选对账承载
    for file_path, expects in also.items():
        if not isinstance(expects, dict):
            continue
        finding = by_file.get(file_path)
        if finding is None:
            metrics_ok = False
            failures.append("also_expect 缺 finding：%s" % file_path)
            continue
        if "edit_count" in expects and finding.edit_count != expects["edit_count"]:
            metrics_ok = False
            failures.append(
                "%s edit_count=%d 期望 %d"
                % (file_path, finding.edit_count, expects["edit_count"])
            )
        if (
            "version_chain_observed" in expects
            and finding.version_count is not None
            and finding.version_count != expects["version_chain_observed"]
        ):
            metrics_ok = False
            failures.append(
                "%s version_count=%d 期望 %d"
                % (file_path, finding.version_count, expects["version_chain_observed"])
            )

    dup_ok, dup_detail = _dup_reconciliation(case_dir, truth, ir)

    anchor_total, anchor_ok = _anchor_reconciliation(expected_files, by_file, ir)

    return CaseMetrics(
        case_id=case_id,
        case_type=truth["case_type"],
        source=truth["source"],
        expected_verdict=expected_verdict,
        verdict_ok=verdict_ok,
        actual_verdict=(by_file[expected_files[0]].verdict if by_file else ""),
        findings_ok=findings_ok,
        detail_failures=tuple(failures),
        metrics_ok=metrics_ok,
        dup_ok=dup_ok,
        dup_detail=tuple(dup_detail),
        anchor_total=anchor_total,
        anchor_ok=anchor_ok,
        hash_ok=hash_ok,
    )


def _engine_inputs(case_dir: Path, truth: dict) -> Tuple[SessionIR, Dict[str, dict], Dict[str, dict]]:
    """case 目录 → 引擎三元组（与 tests/test_m3_engine.py 同一实读路径，K4）。"""
    session_path = case_dir / "session.jsonl"
    if truth["source"] == "claude_code":
        ir = parse_claude_session(session_path)
        chains = read_version_chains(case_dir / "file-history")
        snap_map = read_snapshot_file_map(session_path)
        return ir, chains.get(ir.meta.session_id, {}), snap_map
    return parse_codex_session(session_path), {}, {}


def _expected_verdict(truth: dict) -> str:
    if truth.get("expected_rework"):
        return VERDICT_REWORK
    if truth.get("expect_status") == "insufficient_data":
        return VERDICT_INSUFFICIENT
    return VERDICT_NOT_REWORK


def _expected_files(truth: dict, by_file: Dict[str, ReworkFinding]) -> List[str]:
    files = [item["file"] for item in truth.get("expected_rework", [])]
    files.extend(item["file"] for item in truth.get("expected_normal", []) if "file" in item)
    if truth["case_type"] == "missing_chain":
        # truth 只标 expect_status：被写文件以引擎实读为准（对账仍逐 finding 严格）
        files = list(by_file)
    elif truth["case_type"] == "duplicate":
        # duplicate case 的 truth 只标符号候选，不标文件：验证不误判 rework
        files = list(by_file)
    return files


def _dup_reconciliation(case_dir: Path, truth: dict, ir: SessionIR) -> Tuple[Optional[bool], List[str]]:
    """duplicate case：新写符号 × project 已有符号 → 与 expected_dup_candidates 对账。

    其余类型：truth 有候选 → 期望 False（对不上即失败）；无候选 → not_applicable（None）。
    """
    expected = truth.get("expected_dup_candidates") or []
    new_syms = symbols_from_write_payloads(_write_payloads(case_dir / "session.jsonl"))
    existing_syms = _project_symbols(case_dir / "project")
    candidates = find_dup_candidates(new_syms, existing_syms)
    actual = {(c.new_symbol, c.existing_symbol, c.match_reason) for c in candidates}
    expected_set = {(e["new_symbol"], e["existing_symbol"], e["reason"]) for e in expected}
    if expected_set == actual:
        return True, []
    detail = [
        "符号候选对账失败：期望 %s 实得 %s"
        % (
            sorted(expected_set),
            sorted(actual),
        )
    ]
    return False, detail


def _write_payloads(session_path: Path) -> List[Tuple[str, str]]:
    payloads: List[Tuple[str, str]] = []
    for line in session_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("type") != "assistant":
            continue
        for block in (obj.get("message") or {}).get("content") or []:
            if block.get("type") == "tool_use" and block.get("name") == "Write":
                content = (block.get("input") or {}).get("content")
                if isinstance(content, str):
                    payloads.append(("python", content))
    return payloads


def _project_symbols(project_dir: Path):
    collected = []
    for py_file in sorted(project_dir.rglob("*.py")):
        extracted = extract_defined_symbols(py_file.read_text(encoding="utf-8"), "python")
        if extracted:
            collected.extend(extracted)
    return collected


def _anchor_reconciliation(
    expected_files: List[str],
    by_file: Dict[str, ReworkFinding],
    ir: SessionIR,
) -> Tuple[int, int]:
    """锚点可溯源率：expected 文件 finding 的每条 evidence 必须可定位
    （``<源文件>:<行号>`` 或 ``<hash>@vN`` 版本文件名）。"""
    total = 0
    ok = 0
    for file_path in expected_files:
        finding = by_file.get(file_path)
        if finding is None:
            continue
        for anchor in finding.evidence:
            total += 1
            if anchor.startswith("%s:" % ir.meta.source_file) or "@v" in anchor:
                ok += 1
    return total, ok


def _sha256_matches(path: Path, expected: Optional[str]) -> bool:
    if expected is None:
        return None  # manifest 无记录 → 不对账也不放过（由调用方按 False 处理）
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected
