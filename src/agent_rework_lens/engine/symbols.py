"""符号提取（M3 实现）：从 Write/Edit 文本载荷确定性提取函数/类定义名。

首期仅 Python（``def`` / ``class``）；``language ∉ config.SUPPORTED_SYMBOL_LANGUAGES``
→ 显式"未支持"（不猜测，K7 的同族纪律）。

非 Python 文本传入 Python 提取 → 返回空 tuple（把"提取不到"显式暴露给上游，
不冒充"没有符号"）；调用方按文件扩展名选 language，扩展名不支持 → ``None``
（调用方据此记"未支持语言"披露）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from ..config import SUPPORTED_SYMBOL_LANGUAGES

_DEF_RE = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*\(")
_CLASS_RE = re.compile(r"^[ \t]*class[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*[:({]")


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str  # "function" | "class"
    line_in_payload: int  # 载荷内行号（1 起）


def is_supported_language(language: str) -> bool:
    return language in SUPPORTED_SYMBOL_LANGUAGES


def extract_defined_symbols(text: str, language: str = "python") -> Optional[Tuple[Symbol, ...]]:
    """提取源码文本中的顶层/嵌套 ``def`` / ``class`` 定义名（确定性）。

    返回 ``None`` = 语言未支持（显式拒绝，不猜测）；Python 文本无定义 → 空 tuple。
    """
    if not is_supported_language(language):
        return None
    symbols = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _DEF_RE.match(line)
        if match:
            symbols.append(Symbol(name=match.group(1), kind="function", line_in_payload=line_number))
            continue
        match = _CLASS_RE.match(line)
        if match:
            symbols.append(Symbol(name=match.group(1), kind="class", line_in_payload=line_number))
    return tuple(symbols)
