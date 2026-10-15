"""返工检测引擎（类型冻结；算法 M3 实现）。

判定语义（口径，plan/04 §7.1）：
1. 版本数 ≥ N 或 Edit 次数 ≥ M（阈值见 config.py 单点）→ ``rework``；
2. 两条都不成立且**版本链缺失** → ``insufficient_data``（禁止由 Edit 次数反推版本链，K4）；
3. 两条都不成立且版本链存在 → ``not_rework``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..errors import StageNotReady

VERDICT_REWORK = "rework"
VERDICT_NOT_REWORK = "not_rework"
VERDICT_INSUFFICIENT = "insufficient_data"
VERDICTS = (VERDICT_REWORK, VERDICT_NOT_REWORK, VERDICT_INSUFFICIENT)


@dataclass(frozen=True)
class ReworkFinding:
    """单个文件（单会话内）的返工判定结果；``evidence`` 为证据锚点（源文件行号 / 版本文件名）。"""

    file_path: str
    session_id: str
    verdict: str  # VERDICTS 之一
    version_count: Optional[int] = None  # 版本链缺失 → None（不猜测）
    edit_count: int = 0
    first_edit_seq: Optional[int] = None
    last_edit_seq: Optional[int] = None
    span_seconds: Optional[float] = None  # 时间戳缺失 → None（报告注明）
    reasons: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()


def analyze_rework(*args, **kwargs):
    raise StageNotReady("返工检测引擎", "M3")
