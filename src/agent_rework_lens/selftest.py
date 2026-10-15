"""内置自检（🟢）：任何环境一条命令确认"装好了"；CI 冒烟复用。

自检项（任一 FAIL → 退出码 1）：
1. 版本一致性（未安装 → SKIP 不 FAIL）；
2. 口径存在性（config 阈值与集合合法）；
3. 退出码映射（互异且完整）；
4. 编码护栏（探针逻辑自洽）；
5. 发现探测（本机跑一次，不抛异常；未发现源不视为失败）。
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from typing import Tuple

from . import __version__, config
from . import exitcodes as ec
from .discovery import discover_sources
from .stdio import _ensure_utf8_stdio, _stream_needs_utf8

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"

STATUSES = (STATUS_OK, STATUS_FAIL, STATUS_SKIP)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class SelftestResult:
    checks: Tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return not any(c.status == STATUS_FAIL for c in self.checks)


def run_selftest() -> SelftestResult:
    checks = (
        _check_version_consistency(),
        _check_config_presence(),
        _check_exitcode_map(),
        _check_stdio_guard(),
        _check_discovery_probe(),
    )
    return SelftestResult(checks=checks)


def _check_version_consistency() -> CheckResult:
    name = "版本一致性"
    try:
        installed = importlib.metadata.version(config.TOOL_NAME)
    except importlib.metadata.PackageNotFoundError:
        return CheckResult(name, STATUS_SKIP, "未安装（源码态运行），跳过与分发元数据的比对")
    if installed == __version__:
        return CheckResult(name, STATUS_OK, "分发元数据版本 == 包版本 %s" % __version__)
    return CheckResult(name, STATUS_FAIL, "分发 %s != 包 %s" % (installed, __version__))


def _check_config_presence() -> CheckResult:
    name = "口径存在性（config）"
    problems = []
    if not isinstance(config.REWORK_MIN_VERSIONS, int) or config.REWORK_MIN_VERSIONS < 1:
        problems.append("REWORK_MIN_VERSIONS")
    if not isinstance(config.REWORK_MIN_EDITS, int) or config.REWORK_MIN_EDITS < 1:
        problems.append("REWORK_MIN_EDITS")
    if not (
        isinstance(config.DUP_MATCH_THRESHOLD, float)
        and 0.0 < config.DUP_MATCH_THRESHOLD <= 1.0
    ):
        problems.append("DUP_MATCH_THRESHOLD")
    for set_name in ("READ_EVENT_KINDS", "WRITE_EVENT_KINDS", "SUPPORTED_SYMBOL_LANGUAGES"):
        value = getattr(config, set_name)
        if not isinstance(value, frozenset) or not value:
            problems.append(set_name)
    if config.READ_EVENT_KINDS & config.WRITE_EVENT_KINDS:
        problems.append("READ/WRITE 口径集合重叠")
    if problems:
        return CheckResult(name, STATUS_FAIL, "；".join(problems))
    return CheckResult(name, STATUS_OK, "阈值与口径集合齐备且合法")


def _check_exitcode_map() -> CheckResult:
    name = "退出码映射"
    values = (ec.OK, ec.INTERNAL_ERROR, ec.USAGE_ERROR, ec.NO_SOURCES, ec.STAGE_NOT_READY)
    if len(set(values)) != len(values):
        return CheckResult(name, STATUS_FAIL, "退出码常量存在重复值")
    if values != tuple(ec.ALL_CODES):
        return CheckResult(name, STATUS_FAIL, "ALL_CODES 与常量定义不一致")
    return CheckResult(name, STATUS_OK, "5 个退出码互异且映射完整")


def _check_stdio_guard() -> CheckResult:
    name = "编码护栏"

    class _Cp1252Like:
        encoding = "cp1252"

    class _Cp936Like:
        encoding = "cp936"

    if not _stream_needs_utf8(_Cp1252Like()):
        return CheckResult(name, STATUS_FAIL, "cp1252 探针未识别为需切换（护栏失效）")
    if _stream_needs_utf8(_Cp936Like()):
        return CheckResult(name, STATUS_FAIL, "cp936 探针被误判为需切换（中文控制台会被乱动）")
    _ensure_utf8_stdio([])  # 可调用性（空流列表不触碰真实 stdio）
    return CheckResult(name, STATUS_OK, "探针逻辑自洽（cp1252 切 / cp936 留）")


def _check_discovery_probe() -> CheckResult:
    name = "发现探测"
    try:
        result = discover_sources()
    except Exception as exc:  # 自检要报出，而不是崩溃
        return CheckResult(name, STATUS_FAIL, "discover_sources() 抛异常: %r" % exc)
    return CheckResult(
        name,
        STATUS_OK,
        "本机探测完成（发现 %d 个文件；未发现源不视为失败）" % result.total_files,
    )
