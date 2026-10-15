"""jsonl 逐行容错读取（共享工具）。

坏行**只计数不中断**——解析失败 ≠ 静默跳过（由调用方计入 IR 的 ParseNote）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional, Tuple


def iter_jsonl_lines(path) -> Iterator[Tuple[int, Optional[dict], Optional[str]]]:
    """逐行读取 jsonl 文件。

    yield ``(行号, 解析出的 dict 或 None, 错误信息或 None)``；空行跳过（不计错误）。
    """
    with open(Path(path), "r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_number, None, "malformed_json_line: %s" % exc.msg
                continue
            if not isinstance(obj, dict):
                yield line_number, None, "non_object_json_line"
                continue
            yield line_number, obj, None
