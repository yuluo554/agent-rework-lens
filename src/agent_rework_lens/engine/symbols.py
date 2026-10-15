"""符号提取（M3 实现）：从 Write/Edit 文本载荷确定性提取函数/类定义名。

首期仅 Python（``def`` / ``class``）；``language ∉ config.SUPPORTED_SYMBOL_LANGUAGES``
→ 显式"未支持"（不猜测，K7 的同族纪律）。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import StageNotReady


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str  # "function" | "class"
    line_in_payload: int  # 载荷内行号（1 起）


def extract_defined_symbols(text: str, language: str = "python"):
    raise StageNotReady("符号提取", "M3")
