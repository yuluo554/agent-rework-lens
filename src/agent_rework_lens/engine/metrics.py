"""指标层：Read:Edit 比 + "新建 vs 复用"粗匹配（算法 M3；口径与类型已冻结）。

Read:Edit 比口径：分子 = ``config.READ_EVENT_KINDS`` 计数，分母 = ``config.WRITE_EVENT_KINDS``
计数；分母为 0 → 比值"未定义"（``None``），**不填 0 不填 inf**（plan/04 §7.2）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .. import config
from ..errors import StageNotReady


@dataclass(frozen=True)
class DupCandidate:
    """"新建 vs 复用"粗匹配候选（信号非判决；输出处必须带披露，K5）。"""

    new_symbol: str
    existing_symbol: str
    match_reason: str  # "normalized_exact" | "high_similarity"
    similarity: Optional[float] = None  # normalized_exact 时为 None（或 1.0）
    new_evidence: str = ""
    existing_evidence: str = ""


@dataclass(frozen=True)
class SessionMetrics:
    """会话级指标（writes_by_kind 用有序键值对，保证序列化确定性）。"""

    session_id: str
    reads: int = 0
    writes: int = 0
    writes_by_kind: Tuple[Tuple[str, int], ...] = ()
    read_edit_ratio: Optional[float] = None  # 分母为 0 → None（未定义）
    dup_candidates: Tuple[DupCandidate, ...] = ()


def count_read_write(events: Iterable) -> Tuple[int, int]:
    """按 config 口径集合统计 (reads, writes)。"""
    reads = 0
    writes = 0
    for event in events:
        if event.kind in config.READ_EVENT_KINDS:
            reads += 1
        elif event.kind in config.WRITE_EVENT_KINDS:
            writes += 1
    return reads, writes


def compute_read_edit_ratio(reads: int, writes: int) -> Optional[float]:
    """Read:Edit 比；分母为 0 → None（未定义）。"""
    if writes <= 0:
        return None
    return reads / writes


def find_dup_candidates(*args, **kwargs):
    raise StageNotReady("新建 vs 复用粗匹配", "M3")
