"""Claude Code 会话日志解析器 → SessionIR（M2 实现）。

字段策略：以 data/README.md §2.1 / §2.2 的核对状态为准——
**核对状态 ≠ ✅ 的字段不得进入计算路径**（落 unknown / 跳过并计入 ParseNote，K7）。

M0 骨架护栏：M1 数据核对 → M2 启用；在此之前一切调用以 StageNotReady 明确拦截。
"""

from __future__ import annotations

from ..errors import StageNotReady
from ..ir import SessionIR


def parse_claude_session(path) -> SessionIR:
    raise StageNotReady("Claude Code 会话解析器", "M2（完成 M1 字段核对后）")
