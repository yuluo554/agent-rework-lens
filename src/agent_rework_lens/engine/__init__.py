"""引擎层：返工检测 / Read:Edit 比 / 符号提取 / 粗匹配（M3 实现算法；类型已冻结）。"""

from .metrics import (
    DupCandidate,
    SessionMetrics,
    compute_read_edit_ratio,
    count_read_write,
    find_dup_candidates,
)
from .rework import ReworkFinding, analyze_rework
from .symbols import Symbol, extract_defined_symbols

__all__ = [
    "DupCandidate",
    "ReworkFinding",
    "SessionMetrics",
    "Symbol",
    "analyze_rework",
    "compute_read_edit_ratio",
    "count_read_write",
    "extract_defined_symbols",
    "find_dup_candidates",
]
