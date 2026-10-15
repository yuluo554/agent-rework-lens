"""统一会话 IR（schema v1）——解析层与下游之间的**唯一契约**（★ K3）。

- frozen dataclass + tuple：天然不可变、可比较、无外部状态；
- ``to_json()`` 为 canonical 序列化（``sort_keys`` + 末尾 LF）：同一输入两次解析 →
  逐字节一致（tests/test_ir.py 与 M2 确定性对账锁死）；
- ``kind`` 枚举与双源映射表见 plan/03 §5.2（映射表是 M1 逐项核对的对象）。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

IR_VERSION = 1

# kind 枚举（顺序即注册序，勿随意调整）
KIND_READ = "read"
KIND_EDIT = "edit"
KIND_WRITE = "write"
KIND_MULTIEDIT = "multiedit"
KIND_EXEC = "exec"
KIND_OTHER = "other"
KINDS = (KIND_READ, KIND_EDIT, KIND_WRITE, KIND_MULTIEDIT, KIND_EXEC, KIND_OTHER)


@dataclass(frozen=True)
class SessionMeta:
    source: str  # "claude_code" | "codex"
    session_id: str
    cwd: Optional[str] = None
    started_at: Optional[str] = None  # ISO-8601 字符串；缺失为 None（不猜测）
    source_file: str = ""
    project_slug: Optional[str] = None
    agent_version: Optional[str] = None


@dataclass(frozen=True)
class ToolUseEvent:
    seq: int  # 源文件行号（1 起）——证据锚点的一半
    kind: str  # KINDS 之一
    tool_name: str  # 原始工具名（保真）
    timestamp: Optional[str] = None
    file_path: Optional[str] = None


@dataclass(frozen=True)
class TokenUsageEvent:
    seq: int
    timestamp: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


@dataclass(frozen=True)
class ParseNote:
    """解析注记：坏行计数 / 未核对字段跳过计数等——显式可见，不静默。"""

    code: str
    message: str
    count: int = 1


@dataclass(frozen=True)
class SessionIR:
    meta: SessionMeta
    tool_events: Tuple[ToolUseEvent, ...] = ()
    token_events: Tuple[TokenUsageEvent, ...] = ()
    notes: Tuple[ParseNote, ...] = ()
    ir_version: int = IR_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        """Canonical 序列化：LF 行尾、末尾换行、键序固定、UTF-8 内容不转义。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
