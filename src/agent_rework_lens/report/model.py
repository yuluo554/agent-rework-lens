"""报告模型（渲染输入；渲染器不读时钟/环境，一切以入参为准，K11）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ..engine.metrics import DupCandidate, SessionMetrics
from ..engine.rework import ReworkFinding

# 粗匹配披露文本（K5）：凡输出候选之处必须携带。
DUP_DISCLOSURE = "粗匹配 ≠ 确认重复：以下为候选信号（符号名归一化/高相似度），需人工复核。"


@dataclass(frozen=True)
class ReportMeta:
    title: str
    tool_name: str
    tool_version: str
    source_summary: str = ""  # 数据来源概述（会话数 / 文件数等，由编排层组装）
    thresholds_note: str = ""  # 阈值口径展示（由编排层从 config 运行时读取后传入）


@dataclass(frozen=True)
class ReportModel:
    meta: ReportMeta
    rework_findings: Tuple[ReworkFinding, ...] = ()
    dup_candidates: Tuple[DupCandidate, ...] = ()
    session_metrics: Tuple[SessionMetrics, ...] = ()
    notes: Tuple[str, ...] = ()
