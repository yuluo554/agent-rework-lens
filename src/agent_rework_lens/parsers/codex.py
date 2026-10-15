"""Codex 会话日志解析器 → SessionIR（M2 实现）。

字段策略：以 data/README.md §2.3 的核对状态为准——
``apply_patch`` 目标路径字段等待核对项闭环前，不参与路径级计算（K7）。

M0 骨架护栏：M1 数据核对 → M2 启用；在此之前一切调用以 StageNotReady 明确拦截。
"""

from __future__ import annotations

from ..errors import StageNotReady
from ..ir import SessionIR


def parse_codex_session(path) -> SessionIR:
    raise StageNotReady("Codex 会话解析器", "M2（完成 M1 字段核对后）")
