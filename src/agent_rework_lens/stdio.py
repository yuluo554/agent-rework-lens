"""编码护栏（★ K10）：所有会打印的可执行入口（CLI 与 tools/ 每个脚本）必须先调用本函数。

为什么：Windows 下非交互 stdout 的编码来自系统 locale（CI 是 cp1252、中文控制台是
cp936）。cp1252 无法编码中文 → 打印即 ``UnicodeEncodeError``。
策略（按 stream.encoding 探针决定，不改动本来就能用的流）：

- 探针能编码样例中文 → 不动（中文控制台 cp936 保持原样，显示正常）；
- 不能编码且有 ``reconfigure`` → 切到 utf-8；
- 无 ``reconfigure``（如被重定向为 StringIO）→ 静默跳过。

回归：tests/test_stdio.py 用 ``TextIOWrapper(BytesIO(), encoding="cp1252")`` 复现。
"""

from __future__ import annotations

import sys
from typing import Iterable, Optional

# 只用中文做探针：cp936 可编码（不乱动中文控制台）/ cp1252 与 ascii 不可编码（需要切换）。
PROBE_SAMPLE = "会话返工体检中文"


def _stream_needs_utf8(stream) -> bool:
    """探针：该流当前编码是否无法表示样例中文。"""
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        PROBE_SAMPLE.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return True
    return False


def _ensure_utf8_stdio(streams: Optional[Iterable] = None) -> None:
    """对 stdout / stderr（或显式传入的流）做编码加固；护栏自身绝不成为崩溃点。"""
    if streams is None:
        streams = (sys.stdout, sys.stderr)
    for stream in streams:
        try:
            if stream is None or not _stream_needs_utf8(stream):
                continue
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is None:
                continue
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            # 护栏在异常环境里的职责是"尽力而为"，不因流状态怪异而打断主流程。
            continue
