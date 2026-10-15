"""路径自适应发现（FR-1）：显式参数 > 环境变量 > 常见默认位置。

- 递归发现（实测存在嵌套目录）；空目录跳过；按后缀过滤；
- 输出确定性（排序固定）；不硬编码任何用户名/绝对路径；
- 找不到的源进 ``missing``（含"查过哪里"），**绝不伪造空报告**。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from . import config

KIND_CLAUDE_SESSIONS = "claude_sessions"
KIND_CLAUDE_FILE_HISTORY = "claude_file_history"
KIND_CODEX_SESSIONS = "codex_sessions"

SOURCE_FILTERS = ("auto", "claude", "codex")


@dataclass(frozen=True)
class SourceLocation:
    kind: str
    root: str  # 展示用路径字符串
    files: Tuple[str, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class MissingSource:
    kind: str
    looked_at: Tuple[str, ...]
    hint: str


@dataclass(frozen=True)
class DiscoveryResult:
    locations: Tuple[SourceLocation, ...]
    missing: Tuple[MissingSource, ...]

    @property
    def total_files(self) -> int:
        return sum(loc.file_count for loc in self.locations)


def resolve_claude_home(claude_home: Optional[str] = None) -> Path:
    return _resolve_home(claude_home, config.ENV_CLAUDE_HOME, config.DEFAULT_CLAUDE_HOME)


def resolve_codex_home(codex_home: Optional[str] = None) -> Path:
    return _resolve_home(codex_home, config.ENV_CODEX_HOME, config.DEFAULT_CODEX_HOME)


def _resolve_home(explicit: Optional[str], env_name: str, default: str) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env_value = os.environ.get(env_name)
    if env_value:
        return Path(env_value).expanduser()
    return Path(default).expanduser()


def discover_sources(
    claude_home: Optional[str] = None,
    codex_home: Optional[str] = None,
    source_filter: str = "auto",
) -> DiscoveryResult:
    """发现日志源；``source_filter ∈ {"auto","claude","codex"}``。"""
    if source_filter not in SOURCE_FILTERS:
        raise ValueError("source_filter 必须是 %s 之一，收到: %r" % (SOURCE_FILTERS, source_filter))

    locations = []
    missing = []

    if source_filter in ("auto", "claude"):
        claude_root = resolve_claude_home(claude_home)
        sessions_dir = claude_root / "projects"
        session_files = _find_files(sessions_dir, "*.jsonl")
        if session_files:
            locations.append(SourceLocation(KIND_CLAUDE_SESSIONS, str(sessions_dir), session_files))
        else:
            missing.append(
                MissingSource(
                    KIND_CLAUDE_SESSIONS,
                    (str(sessions_dir),),
                    "未发现 Claude Code 会话日志；可用 --claude-home 或环境变量 %s 指定位置"
                    % config.ENV_CLAUDE_HOME,
                )
            )

        history_dir = claude_root / "file-history"
        history_files = _find_files(history_dir, "*@v*")
        if history_files:
            locations.append(
                SourceLocation(KIND_CLAUDE_FILE_HISTORY, str(history_dir), history_files)
            )
        else:
            missing.append(
                MissingSource(
                    KIND_CLAUDE_FILE_HISTORY,
                    (str(history_dir),),
                    "未发现 Claude Code 文件版本快照（file-history）；返工检测将缺该会话的版本链",
                )
            )

    if source_filter in ("auto", "codex"):
        codex_root = resolve_codex_home(codex_home)
        codex_sessions_dir = codex_root / "sessions"
        codex_files = _find_files(codex_sessions_dir, "*.jsonl")
        if codex_files:
            locations.append(
                SourceLocation(KIND_CODEX_SESSIONS, str(codex_sessions_dir), codex_files)
            )
        else:
            missing.append(
                MissingSource(
                    KIND_CODEX_SESSIONS,
                    (str(codex_sessions_dir),),
                    "未发现 Codex 会话日志；可用 --codex-home 或环境变量 %s 指定位置"
                    % config.ENV_CODEX_HOME,
                )
            )

    # 确定性输出：按 (kind, root) 排序
    locations.sort(key=lambda loc: (loc.kind, loc.root))
    missing.sort(key=lambda m: m.kind)
    return DiscoveryResult(locations=tuple(locations), missing=tuple(missing))


def _find_files(directory: Path, pattern: str) -> Tuple[str, ...]:
    """递归按模式找文件；目录不存在或空 → 空元组。排序固定保证确定性。"""
    if not directory.is_dir():
        return ()
    found = []
    for path in sorted(directory.rglob(pattern), key=str):
        if path.is_file():
            found.append(str(path))
    return tuple(found)
