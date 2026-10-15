"""CLI：argparse + 退出码契约（K2）+ 编码护栏（K10）。

K8 双通路：``python -m agent_rework_lens`` 与 ``arl`` 命令共用本 ``main()``。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import __version__, config
from . import exitcodes as ec
from .benchmark.runner import run_bench
from .discovery import SOURCE_FILTERS
from .engine.rework import VERDICT_INSUFFICIENT, VERDICT_NOT_REWORK
from .errors import NoSourcesFound
from .pipeline import run_scan, run_sources
from .selftest import run_selftest
from .stdio import _ensure_utf8_stdio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=config.COMMAND_NAME,
        description="%s —— AI 代码\"重复造轮子 + 返工\"体检器（纯本地、零上传、确定性计数）"
        % config.TOOL_NAME,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%s %s" % (config.TOOL_NAME, __version__),
        help="打印版本并退出",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="打印工具名称与版本")

    sources = subparsers.add_parser("sources", help="列出本机发现的日志源与文件数")
    _add_source_args(sources)
    sources.add_argument("--json", action="store_true", help="输出机读 JSON")

    scan = subparsers.add_parser("scan", help="发现 → 解析 → IR 摘要（引擎结论 M3 接入）")
    _add_source_args(scan)

    selftest = subparsers.add_parser("selftest", help="内置自检")
    selftest.add_argument("--json", action="store_true", help="输出机读 JSON")

    bench = subparsers.add_parser("bench", help="合成会话基准评测（truth 对账 + 覆盖率门槛）")
    bench.add_argument(
        "--data-dir",
        default=None,
        help="基准数据目录（默认仓库内 data/synthetic；缺失 → 套件未启用，退出码 1）",
    )
    bench.add_argument("--json", action="store_true", help="输出机读 JSON")

    return parser


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--claude-home", default=None, help="Claude 数据目录（默认 ~/.claude）")
    parser.add_argument("--codex-home", default=None, help="Codex 数据目录（默认 ~/.codex）")
    parser.add_argument(
        "--source",
        choices=list(SOURCE_FILTERS),
        default="auto",
        help="限定日志源（默认 auto：Claude + Codex）",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    _ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "version":
            print("%s %s" % (config.TOOL_NAME, __version__))
            return ec.OK
        if args.command == "sources":
            return _cmd_sources(args)
        if args.command == "scan":
            return _cmd_scan(args)
        if args.command == "selftest":
            return _cmd_selftest(args)
        if args.command == "bench":
            return _cmd_bench(args)
    except NoSourcesFound as exc:
        print(exc.detail or "未发现可分析日志源。", file=sys.stderr)
        return ec.NO_SOURCES

    # argparse 已保证命令走遍全部分支；防御性兜底
    parser.error("未知命令: %r" % (args.command,))
    return ec.USAGE_ERROR


def _cmd_sources(args: argparse.Namespace) -> int:
    outcome = run_sources(args.claude_home, args.codex_home, args.source)
    discovery = outcome.discovery

    if args.json:
        payload = {
            "command": "sources",
            "locations": [
                {
                    "kind": loc.kind,
                    "root": loc.root,
                    "file_count": loc.file_count,
                    "files": list(loc.files),
                }
                for loc in discovery.locations
            ],
            "missing": [
                {"kind": m.kind, "looked_at": list(m.looked_at), "hint": m.hint}
                for m in discovery.missing
            ],
            "total_files": discovery.total_files,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return ec.OK

    if not outcome.found_any:
        print("未发现可分析日志源。已检查：")
        for m in discovery.missing:
            print("  - %s：%s" % (m.kind, " | ".join(m.looked_at)))
        print(
            "提示：可用 --claude-home/--codex-home 或环境变量 %s/%s 指定日志位置。"
            % (config.ENV_CLAUDE_HOME, config.ENV_CODEX_HOME)
        )
        return ec.OK

    print("发现日志源（共 %d 个文件）：" % discovery.total_files)
    for loc in discovery.locations:
        print("  - %s：%d 个文件（%s）" % (loc.kind, loc.file_count, loc.root))
    for m in discovery.missing:
        print("  - [未发现] %s：%s" % (m.kind, " | ".join(m.looked_at)))
    return ec.OK


def _cmd_scan(args: argparse.Namespace) -> int:
    outcome = run_scan(args.claude_home, args.codex_home, args.source)

    print(
        "scan 完成：%d 个会话，%d 个工具事件，%d 个 token 事件，%d 条解析注记"
        % (
            len(outcome.sessions),
            outcome.tool_event_count,
            outcome.token_event_count,
            outcome.note_count,
        )
    )
    # 引擎摘要（M3）：阈值取 config 运行时值（K1 单点引用）；判定零外链零时钟（K6/K11）
    print(
        "返工判定（阈值：版本 ≥ %d 或编辑 ≥ %d）：%d 项 rework / %d 项 insufficient_data / %d 项 not_rework"
        % (
            config.REWORK_MIN_VERSIONS,
            config.REWORK_MIN_EDITS,
            outcome.rework_count,
            sum(1 for f in outcome.findings if f.verdict == VERDICT_INSUFFICIENT),
            sum(1 for f in outcome.findings if f.verdict == VERDICT_NOT_REWORK),
        )
    )
    for session in outcome.sessions:
        meta = session.ir.meta
        chain_summary = "，版本链 %d 条" % len(session.version_chains) if session.version_chains else ""
        print(
            "  - [%s] %s：工具事件 %d，写事件 %d%s"
            % (
                meta.source,
                meta.session_id,
                len(session.ir.tool_events),
                session.write_event_count,
                chain_summary,
            )
        )
        for note in session.ir.notes:
            print("    [note] %s ×%d：%s" % (note.code, note.count, note.message))
    for finding in outcome.findings:
        span = "%.0fs" % finding.span_seconds if finding.span_seconds is not None else "未知（时间戳缺失）"
        print(
            "  [verdict] %s %s：版本 %s / 编辑 %d / 跨度 %s / 理由 %s"
            % (
                finding.verdict,
                finding.file_path,
                "缺失" if finding.version_count is None else str(finding.version_count),
                finding.edit_count,
                span,
                ",".join(finding.reasons),
            )
        )
        for anchor in finding.evidence:
            print("    [evidence] %s" % anchor)
    return ec.OK


def _cmd_selftest(args: argparse.Namespace) -> int:
    result = run_selftest()
    if args.json:
        payload = {
            "command": "selftest",
            "ok": result.ok,
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail} for c in result.checks
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        for c in result.checks:
            print("[%s] %s — %s" % (c.status, c.name, c.detail or ""))
    return ec.OK if result.ok else ec.INTERNAL_ERROR


def _cmd_bench(args: argparse.Namespace) -> int:
    """合成基准评测（plan/04 §9）。

    退出码三语义：0 = 达标；1 = 未达标/未启用（明确清单，不冒充通过）；2 = 用法
    （argparse 层）。人读输出中文、机读 JSON 确定性（sort_keys）。
    """
    result = run_bench(args.data_dir)

    if args.json:
        payload = {
            "command": "bench",
            "data_dir": result.data_dir,
            "not_enabled": result.not_enabled,
            "not_enabled_detail": result.not_enabled_detail,
            "manifest_schema": result.manifest_schema,
            "passed": result.passed,
            "coverage": {
                "required": dict(sorted(result.coverage.required.items())),
                "actual": dict(sorted(result.coverage.actual.items())),
            },
            "summary": {
                "case_count": result.case_count,
                "rework_hit": result.rework_hit,
                "rework_total": result.rework_total,
                "false_positive": result.false_positive,
                "not_rework_total": result.not_rework_total,
                "anchor_ok": result.anchor_ok,
                "anchor_total": result.anchor_total,
            },
            "cases": [
                {
                    "case_id": c.case_id,
                    "case_type": c.case_type,
                    "source": c.source,
                    "expected_verdict": c.expected_verdict,
                    "ok": c.ok,
                    "verdict_ok": c.verdict_ok,
                    "metrics_ok": c.metrics_ok,
                    "dup_ok": c.dup_ok,
                    "hash_ok": c.hash_ok,
                    "anchor_ok": c.anchor_ok,
                    "anchor_total": c.anchor_total,
                    "failures": c.failures(),
                }
                for c in result.cases
            ],
            "failures": result.failures(),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return ec.OK if result.passed else ec.INTERNAL_ERROR

    if result.not_enabled:
        print("基准套件未启用：%s" % result.not_enabled_detail)
        print("说明：未启用 ≠ 通过（空分母不冒充满分）。退出码 1。")
        return ec.INTERNAL_ERROR

    print(
        "合成基准评测（%s）：manifest schema=%s"
        % (result.data_dir, result.manifest_schema)
    )
    print(
        "覆盖率门槛（数值只来自 manifest）：要求 %s / 实际 %s"
        % (
            dict(sorted(result.coverage.required.items())),
            dict(sorted(result.coverage.actual.items())),
        )
    )
    print(
        "对账汇总：%d 样例；rework 命中 %d/%d；误报 %d/%d（not_rework 总数）；锚点可溯源 %d/%d"
        % (
            result.case_count,
            result.rework_hit,
            result.rework_total,
            result.false_positive,
            result.not_rework_total,
            result.anchor_ok,
            result.anchor_total,
        )
    )
    for case in result.cases:
        status = "OK" if case.ok else "FAIL"
        line = "  [%s] %s（%s/%s → 期望 %s）" % (
            status,
            case.case_id,
            case.source,
            case.case_type,
            case.expected_verdict,
        )
        if case.ok:
            print(line)
        else:
            print(line)
            for failure in case.failures():
                print("      - %s" % failure)
    for failure in result.coverage.failures():
        print("  [覆盖率] %s" % failure)
    if result.passed:
        print("结论：达标。")
        return ec.OK
    print("结论：未达标（清单见上）。退出码 1。")
    return ec.INTERNAL_ERROR
