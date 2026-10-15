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
