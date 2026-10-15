"""指标层：Read:Edit 比 + "新建 vs 复用"粗匹配（plan/04 §7.2/§7.4 冻结口径，M3 实现）。

Read:Edit 比口径：分子 = ``config.READ_EVENT_KINDS`` 计数，分母 = ``config.WRITE_EVENT_KINDS``
计数；分母为 0 → 比值"未定义"（``None``），**不填 0 不填 inf**（plan/04 §7.2）。

粗匹配归一化（plan/04 §7.4 冻结步骤）：① 转小写；② ``-`` → ``_``；③ 去首尾 ``_``；
④ 按 ``_`` 切分，**首 token** 命中 ``SYMBOL_PREFIX_TOKENS`` 或 **尾 token** 命中
``SYMBOL_SUFFIX_TOKENS`` → 剔除（可迭代）；⑤ 剩余 token 拼接（去分隔符）。
匹配：归一化精确相等 → ``normalized_exact``；否则 ``difflib`` ratio ≥
``DUP_MATCH_THRESHOLD`` → ``high_similarity``（附 ratio）。

**披露制（K5）**：任何候选输出必须伴随 ``DUP_DISCLOSURE`` 文本——本模块提供
``DUP_DISCLOSURE`` 单点常量（report 层从 report.model 引用同一文本；两处经测试锁定一致）。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .. import config
from ..ir import ToolUseEvent
from .symbols import Symbol, extract_defined_symbols

DUP_DISCLOSURE = "粗匹配 ≠ 确认重复：以下为候选信号（符号名归一化/高相似度），需人工复核。"


@dataclass(frozen=True)
class DupCandidate:
    """"新建 vs 复用"粗匹配候选（信号非判决；输出处必须带披露，K5）。"""

    new_symbol: str
    existing_symbol: str
    match_reason: str  # "normalized_exact" | "high_similarity"
    similarity: Optional[float] = None  # normalized_exact 时为 None（或 1.0）
    new_evidence: str = ""
    existing_evidence: str = ""


@dataclass(frozen=True)
class SessionMetrics:
    """会话级指标（writes_by_kind 用有序键值对，保证序列化确定性）。"""

    session_id: str
    reads: int = 0
    writes: int = 0
    writes_by_kind: Tuple[Tuple[str, int], ...] = ()
    read_edit_ratio: Optional[float] = None  # 分母为 0 → None（未定义）
    dup_candidates: Tuple[DupCandidate, ...] = ()


def count_read_write(events: Iterable) -> Tuple[int, int]:
    """按 config 口径集合统计 (reads, writes)。"""
    reads = 0
    writes = 0
    for event in events:
        if event.kind in config.READ_EVENT_KINDS:
            reads += 1
        elif event.kind in config.WRITE_EVENT_KINDS:
            writes += 1
    return reads, writes


def compute_read_edit_ratio(reads: int, writes: int) -> Optional[float]:
    """Read:Edit 比；分母为 0 → None（未定义）。"""
    if writes <= 0:
        return None
    return reads / writes


def normalize_symbol_name(name: str) -> str:
    """plan/04 §7.4 冻结的 5 步归一化（词表来自 config 单点）。"""
    lowered = name.lower()
    underscored = lowered.replace("-", "_")
    stripped = underscored.strip("_")
    tokens = [token for token in stripped.split("_") if token]
    changed = True
    while changed and tokens:
        changed = False
        if tokens and tokens[0] in config.SYMBOL_PREFIX_TOKENS:
            tokens.pop(0)
            changed = True
        if tokens and tokens[-1] in config.SYMBOL_SUFFIX_TOKENS:
            tokens.pop()
            changed = True
    return "".join(tokens)


def match_symbols(new_symbol: str, existing_symbol: str) -> Optional[Tuple[str, Optional[float]]]:
    """plan/04 §7.4 冻结的两级匹配；未命中 → None。"""
    if normalize_symbol_name(new_symbol) == normalize_symbol_name(existing_symbol):
        return ("normalized_exact", None)
    ratio = difflib.SequenceMatcher(None, new_symbol, existing_symbol).ratio()
    if ratio >= config.DUP_MATCH_THRESHOLD:
        return ("high_similarity", ratio)
    return None


def find_dup_candidates(
    new_symbols: Iterable[Symbol],
    existing_symbols: Iterable[Symbol],
    new_evidence: str = "",
    existing_evidence: str = "",
) -> Tuple[DupCandidate, ...]:
    """新写符号 × 已有符号 → 粗匹配候选（确定性：输出按 (new, existing) 排序去重）。"""
    existing = list(existing_symbols)
    candidates: List[DupCandidate] = []
    for new in new_symbols:
        for existing_symbol in existing:
            if new.name == existing_symbol.name:
                continue
            matched = match_symbols(new.name, existing_symbol.name)
            if matched is None:
                continue
            reason, similarity = matched
            candidates.append(
                DupCandidate(
                    new_symbol=new.name,
                    existing_symbol=existing_symbol.name,
                    match_reason=reason,
                    similarity=similarity,
                    new_evidence=new_evidence,
                    existing_evidence=existing_evidence,
                )
            )
    deduped = {
        (c.new_symbol, c.existing_symbol, c.match_reason): c for c in candidates
    }
    return tuple(
        sorted(deduped.values(), key=lambda c: (c.new_symbol, c.existing_symbol, c.match_reason))
    )


def symbols_from_write_payloads(
    payloads: Iterable[Tuple[str, str]],
) -> Tuple[Symbol, ...]:
    """从 ``(language, source_text)`` 序列提取符号；未支持语言 → 跳过（上游记披露）。"""
    symbols: List[Symbol] = []
    for language, text in payloads:
        extracted = extract_defined_symbols(text, language)
        if extracted is None:
            continue
        symbols.extend(extracted)
    return tuple(symbols)


def compute_session_metrics(
    session_id: str,
    events: Iterable[ToolUseEvent],
    write_payloads: Iterable[Tuple[str, str]] = (),
    existing_symbols: Iterable[Symbol] = (),
    new_evidence: str = "",
    existing_evidence: str = "",
) -> SessionMetrics:
    """会话级指标汇总（确定性；不读时钟/环境，K11）。"""
    event_list = list(events)
    reads, writes = count_read_write(event_list)
    by_kind: List[Tuple[str, int]] = []
    for kind in config.WRITE_EVENT_KINDS:
        count = sum(1 for e in event_list if e.kind == kind)
        if count:
            by_kind.append((kind, count))
    by_kind.sort()
    new_syms = symbols_from_write_payloads(write_payloads) if write_payloads else ()
    candidates = (
        find_dup_candidates(new_syms, existing_symbols, new_evidence, existing_evidence)
        if new_syms and existing_symbols
        else ()
    )
    return SessionMetrics(
        session_id=session_id,
        reads=reads,
        writes=writes,
        writes_by_kind=tuple(by_kind),
        read_edit_ratio=compute_read_edit_ratio(reads, writes),
        dup_candidates=candidates,
    )
