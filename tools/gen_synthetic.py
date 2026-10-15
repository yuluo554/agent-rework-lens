# -*- coding: utf-8 -*-
"""合成会话冻结 fixtures 生成器（★ M1 数据先行；plan/05 §四）。

确定性硬约束（★ K9/K11）：
- 自研 splitmix64 RNG，固定 seed；**禁 stdlib random**、禁 set/dict 迭代序入输出、禁系统时钟；
- 所有时间戳为固定常量；输出 UTF-8 无 BOM + LF + 固定字段序；
- 两次运行逐字节一致；``--check`` 重生成与现有冻结件逐字节比对。

样本矩阵（7 类，plan/05 §4.2；阈值**读 config，不抄数值** ★ K1）：
  rework / duplicate / normal / missing_chain / single_edit / threshold_exact / near_miss

形态忠实度（M1 字段核对回填，data/README §2.1/§2.3）：
- Claude 行形如 ``{"type": ..., "sessionId": ..., "timestamp": ..., "message": {...}}``；
  工具调用在 ``message.content[]`` 的 ``tool_use``；快照行 ``snapshot.trackedFileBackups``
  为 dict（键 = 真实文件路径），entry 固定 4 字段；
- Codex 行形如 ``{"type": "response_item", "timestamp": ..., "ordinal": N, "payload": {...}}``；
  ``apply_patch`` 的目标文件路径在 ``payload.input``（V4A 文本）的
  ``*** Update File: <path>`` / ``*** Add File: <path>`` 指令行内。

真值 = 生成时同步程序化标注（truth.json），与样例同源同版本；
冻结目录由 manifest.json 登记 sha256；改动走本生成器整目录重生成，**禁手改**。

用法：
  py -X utf8 tools/gen_synthetic.py            # 生成/重生成到 data/synthetic/
  py -X utf8 tools/gen_synthetic.py --check    # 重生成并与现有冻结件逐字节比对（有差异 exit 1）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# K10：tools/ 每个脚本第一行纪律——先挂数编码护栏再打印。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agent_rework_lens.stdio import _ensure_utf8_stdio  # noqa: E402

from agent_rework_lens.config import (  # noqa: E402
    DUP_MATCH_THRESHOLD,
    REWORK_MIN_EDITS,
    REWORK_MIN_VERSIONS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "synthetic"
MANIFEST_PATH = OUT_DIR / "manifest.json"
SEED = 20261015

# ── 覆盖度门槛（数值只在 manifest 一处；生成器校验各类型例数 ≥ 门槛） ──
MIN_COUNT_BY_TYPE = {
    "rework": 2,
    "duplicate": 2,
    "normal": 2,
    "missing_chain": 1,
    "single_edit": 1,
    "threshold_exact": 1,
    "near_miss": 1,
}

# ── 固定常量时间戳（K11：不取 now；按 5 分钟步进，够 30+ 个事件用） ──
ISO_STEPS = ["2026-01-05T09:%02d:00.000Z" % m for m in range(0, 60, 5)] + [
    "2026-01-05T10:%02d:00.000Z" % m for m in range(0, 60, 5)
]


def iso_at(step: int) -> str:
    return ISO_STEPS[step % len(ISO_STEPS)]


# ── 假名白名单（与 manifest.whitelist 同源；K9 登记制） ──
FAKE_PROJECTS = ("demo-project-alpha", "demo-project-beta")
FAKE_USERS = ("demo-user",)
FAKE_HOSTS = ("demo-host",)
SID_TEMPLATE = "00000000-0000-4000-8000-0000000000{:02d}"  # NN = 01..99
FAKE_POSIX_ROOTS = ("/demo/alpha/src", "/demo/beta/src")


class SplitMix64:
    """自研确定性 RNG（splitmix64 形态）——不引入任何随机源。"""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def next_int(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return z ^ (z >> 31)


def fake_sid(n: int) -> str:
    return SID_TEMPLATE.format(n % 100)


def short_hash(token: str) -> str:
    """确定性"哈希感"快照文件名：sha256(token) 前 16 位（合成可复现，非真实数据）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def fake_module_source(module: str, symbol: str, body: str) -> str:
    return (
        f"def {symbol}(value):\n"
        f'    """{module}.{symbol} demo."""\n'
        f"    {body}\n"
        f"    return value\n"
    )


# ── Claude 行构造（字段序 = 实测形态的骨架序） ──────────────────────────


def claude_meta(sid: str, ts: str, cwd: str) -> str:
    rec = {
        "type": "session_meta_like",
        "sessionId": sid,
        "session_id": sid,
        "timestamp": ts,
        "cwd": cwd,
        "version": "0.0.0-demo",
    }
    return json.dumps(rec, ensure_ascii=False)


def claude_assistant_tooluse(name: str, input_: dict, ts: str, sid: str) -> str:
    rec = {
        "type": "assistant",
        "sessionId": sid,
        "session_id": sid,
        "timestamp": ts,
        "cwd": FAKE_POSIX_ROOTS[0],
        "message": {
            "role": "assistant",
            "type": "message",
            "id": f"msg_demo_{short_hash(name + ts + sid)}",
            "content": [{"type": "tool_use", "name": name, "input": input_}],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_input_tokens": 0,
            },
        },
    }
    return json.dumps(rec, ensure_ascii=False)


def claude_user_toolresult(content: str, ts: str, sid: str) -> str:
    rec = {
        "type": "user",
        "sessionId": sid,
        "session_id": sid,
        "timestamp": ts,
        "cwd": FAKE_POSIX_ROOTS[0],
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": content}],
        },
    }
    return json.dumps(rec, ensure_ascii=False)


def claude_snapshot(tfb: dict, ts: str, sid: str, msg_id: str) -> str:
    """快照行（实测形态：顶层无 timestamp，时间戳在 snapshot 内）。"""
    rec = {
        "type": "file-history-snapshot",
        "sessionId": sid,
        "messageId": msg_id,
        "isSnapshotUpdate": True,
        "snapshot": {"trackedFileBackups": tfb, "timestamp": ts, "messageId": msg_id},
    }
    return json.dumps(rec, ensure_ascii=False)


# ── Codex 行构造 ─────────────────────────────────────────────────────────


def codex_meta(sid: str, ts: str, ordinal: int) -> str:
    rec = {
        "type": "session_meta",
        "timestamp": ts,
        "ordinal": ordinal,
        "payload": {
            "session_id": sid,
            "id": sid,
            "timestamp": ts,
            "cwd": FAKE_POSIX_ROOTS[0],
            "originator": "demo-agent",
            "cli_version": "0.0.0-demo",
            "source": "demo",
        },
    }
    return json.dumps(rec, ensure_ascii=False)


def codex_exec(cmd: str, ts: str, ordinal: int, call_id: str) -> str:
    rec = {
        "type": "response_item",
        "timestamp": ts,
        "ordinal": ordinal,
        "payload": {
            "type": "function_call",
            "name": "exec",
            "call_id": call_id,
            "status": "completed",
            "arguments": json.dumps({"command": [cmd]}, ensure_ascii=False),
        },
    }
    return json.dumps(rec, ensure_ascii=False)


def codex_apply_patch(update_targets: list, add_targets: list, ts: str, ordinal: int, call_id: str) -> str:
    """Codex apply_patch：payload.input = V4A 补丁文本（目标文件路径在指令行内）。"""
    lines = ["*** Begin Patch"]
    for p in update_targets:
        lines.append(f"*** Update File: {p}")
        lines.append("@@")
        lines.append("-old line")
        lines.append("+new line")
    for p in add_targets:
        lines.append(f"*** Add File: {p}")
        lines.append("+def demo_added():")
        lines.append("+    return 1")
    lines.append("*** End Patch")
    rec = {
        "type": "response_item",
        "timestamp": ts,
        "ordinal": ordinal,
        "payload": {
            "type": "custom_tool_call",
            "name": "apply_patch",
            "call_id": call_id,
            "status": "completed",
            "input": "\n".join(lines) + "\n",
        },
    }
    return json.dumps(rec, ensure_ascii=False)


# ── 7 类样本构造（真值同步标注） ─────────────────────────────────────────


def build_rework_claude(idx: int, versions: int) -> dict:
    """rework / threshold_exact 共用骨架：同一文件被连续 Edit versions 次。

    versions = N → 恰好卡阈值（"≥ N"含等于 → 应命中）。
    Claude 版本链语义（M1 核对结论）：@vN = 第 N 次编辑**前**的备份。
    """
    sid = fake_sid(10 + idx)
    mod, sym = "alpha_a", "compute"
    proj_root = FAKE_POSIX_ROOTS[0]
    target = f"{proj_root}/{mod}.py"
    hashname = short_hash(f"{sid}-{mod}-{sym}")

    lines = [claude_meta(sid, iso_at(0), proj_root)]
    lines.append(claude_assistant_tooluse("Read", {"file_path": target}, iso_at(1), sid))
    lines.append(claude_user_toolresult("ok", iso_at(1), sid))
    history: dict[str, bytes] = {}
    # 内容链：vN 内容 = 第 N 次编辑前状态（step = N-1）
    for i in range(1, versions + 1):
        old_line, new_line = f"    step = {i - 1}", f"    step = {i}"
        lines.append(
            claude_assistant_tooluse(
                "Edit",
                {"file_path": target, "old_string": old_line, "new_string": new_line},
                iso_at(2 * i),
                sid,
            )
        )
        lines.append(
            claude_snapshot(
                {
                    target: {
                        "backupFileName": f"{hashname}@v{i}",
                        "version": i,
                        "backupTime": iso_at(2 * i),
                        "realParentDir": proj_root,
                    }
                },
                iso_at(2 * i),
                sid,
                f"msg_demo_snap{i:02d}",
            )
        )
        lines.append(claude_user_toolresult("ok", iso_at(2 * i), sid))
        history[f"file-history/{sid}/{hashname}@v{i}"] = fake_module_source(
            mod, sym, f"step = {i - 1}"
        ).encode("utf-8")

    hit = versions >= REWORK_MIN_VERSIONS
    truth = {
        "case_type": "rework" if hit else "threshold_exact",
        "source": "claude_code",
        "session_id": sid,
        "expected_rework": (
            [
                {
                    "file": target,
                    "reason": "versions",
                    "min_versions": versions,
                    "edit_count": versions,
                }
            ]
            if hit
            else []
        ),
        "expected_dup_candidates": [],
        "expected_normal": [],
        "expect_status": "rework_hit" if hit else "rework_hit",
        "also_expect": {target: {"edit_count": versions, "version_chain_observed": versions}},
        "threshold_note": (
            f"版本数恰好 = REWORK_MIN_VERSIONS（≥ 判据含等于 → 应命中）"
            if not hit
            else f"版本链 {versions} ≥ REWORK_MIN_VERSIONS → 应命中"
        ),
    }
    return {
        "sid": sid,
        "source": "claude_code",
        "session_lines": lines,
        "file_history": history,
        "project": {f"{mod}.py": fake_module_source(mod, sym, f"step = {versions}").encode("utf-8")},
        "truth": truth,
    }


def build_normal_claude(idx: int) -> dict:
    sid = fake_sid(20 + idx)
    proj_root = FAKE_POSIX_ROOTS[0]
    target = f"{proj_root}/beta_a.py"
    content = fake_module_source("beta_a", "render", "mode = 'final'")
    lines = [
        claude_meta(sid, iso_at(0), proj_root),
        claude_assistant_tooluse("Read", {"file_path": target}, iso_at(1), sid),
        claude_user_toolresult("ok", iso_at(1), sid),
        claude_assistant_tooluse(
            "Write", {"file_path": target, "content": content}, iso_at(2), sid
        ),
        claude_user_toolresult("ok", iso_at(2), sid),
    ]
    return {
        "sid": sid,
        "source": "claude_code",
        "session_lines": lines,
        "file_history": {},
        "project": {"beta_a.py": content.encode("utf-8")},
        "truth": {
            "case_type": "normal",
            "source": "claude_code",
            "session_id": sid,
            "expected_rework": [],
            "expected_dup_candidates": [],
            "expected_normal": [{"file": target, "edit_count": 1}],
            "expect_status": "not_rework",
            "also_expect": {},
            "threshold_note": "单次 Write 一次成型、无版本链 → 两条判据均不命中",
        },
    }


def build_duplicate_claude(idx: int, near_miss: bool = False) -> dict:
    """duplicate（归一化后精确相等 → 候选）与 near_miss（低于阈值 → 不命中）共用骨架。

    已有符号 make_compute_helper ↔ 新符号：
      - duplicate:  make_compute_wrapper（归一化同为 "compute" → normalized_exact）
      - near_miss:  compute_parse_validator（归一化相似度 < DUP_MATCH_THRESHOLD → miss）
    """
    sid = fake_sid(30 + idx)
    proj_root = FAKE_POSIX_ROOTS[0]
    existing_sym = "make_compute_helper"
    new_sym = "compute_parse_validator" if near_miss else "make_compute_wrapper"
    target = f"{proj_root}/beta_b.py"
    existing_file = f"{proj_root}/common.py"
    lines = [
        claude_meta(sid, iso_at(0), proj_root),
        claude_assistant_tooluse("Read", {"file_path": existing_file}, iso_at(1), sid),
        claude_user_toolresult("ok", iso_at(1), sid),
        claude_assistant_tooluse(
            "Write",
            {"file_path": target, "content": fake_module_source("beta_b", new_sym, "kind = 'new'")},
            iso_at(2),
            sid,
        ),
        claude_user_toolresult("ok", iso_at(2), sid),
    ]
    if near_miss:
        truth = {
            "case_type": "near_miss",
            "source": "claude_code",
            "session_id": sid,
            "expected_rework": [],
            "expected_dup_candidates": [],
            "expected_normal": [{"file": target, "edit_count": 1}],
            "expect_status": "not_rework",
            "also_expect": {"dup_candidate_expected": False},
            "threshold_note": "符号名近但不重：归一化相似度 < DUP_MATCH_THRESHOLD → 不应命中（反向样例）",
        }
    else:
        truth = {
            "case_type": "duplicate",
            "source": "claude_code",
            "session_id": sid,
            "expected_rework": [],
            "expected_dup_candidates": [
                {
                    "new_symbol": new_sym,
                    "existing_symbol": existing_sym,
                    "reason": "normalized_exact",
                }
            ],
            "expected_normal": [],
            "expect_status": "not_rework",
            "also_expect": {"dup_candidate_expected": True},
            "threshold_note": "新写符号与项目已有符号归一化后精确相等 → 候选（披露制：非克隆判决）",
        }
    return {
        "sid": sid,
        "source": "claude_code",
        "session_lines": lines,
        "file_history": {},
        "project": {
            "common.py": fake_module_source("common", existing_sym, "kind = 'existing'").encode("utf-8"),
            "beta_b.py": fake_module_source("beta_b", new_sym, "kind = 'new'").encode("utf-8"),
        },
        "truth": truth,
    }


def build_missing_chain_claude(idx: int) -> dict:
    sid = fake_sid(40 + idx)
    proj_root = FAKE_POSIX_ROOTS[1]
    target = f"{proj_root}/alpha_b.py"
    lines = [
        claude_meta(sid, iso_at(0), proj_root),
        claude_assistant_tooluse("Read", {"file_path": target}, iso_at(1), sid),
        claude_user_toolresult("ok", iso_at(1), sid),
        claude_assistant_tooluse(
            "Edit",
            {"file_path": target, "old_string": "    step = 0", "new_string": "    step = 1"},
            iso_at(2),
            sid,
        ),
        claude_user_toolresult("ok", iso_at(2), sid),
    ]
    # 关键：有写行为但无任何 file-history 快照 → 版本链缺失（K4：禁止反推）
    return {
        "sid": sid,
        "source": "claude_code",
        "session_lines": lines,
        "file_history": {},
        "project": {"alpha_b.py": fake_module_source("alpha_b", "parse", "step = 1").encode("utf-8")},
        "truth": {
            "case_type": "missing_chain",
            "source": "claude_code",
            "session_id": sid,
            "expected_rework": [],
            "expected_dup_candidates": [],
            "expected_normal": [],
            "expect_status": "insufficient_data",
            "also_expect": {},
            "threshold_note": "有写行为但无版本快照链 → insufficient_data",
        },
    }


def build_single_edit_claude(idx: int) -> dict:
    """single_edit：v1 语义下的最小链（1 次 Edit + 1 个 @v1 快照）→ 不应命中。"""
    sid = fake_sid(50 + idx)
    proj_root = FAKE_POSIX_ROOTS[0]
    target = f"{proj_root}/common.py"
    hashname = short_hash(f"{sid}-common")
    lines = [
        claude_meta(sid, iso_at(0), proj_root),
        claude_assistant_tooluse("Read", {"file_path": target}, iso_at(1), sid),
        claude_user_toolresult("ok", iso_at(1), sid),
        claude_assistant_tooluse(
            "Edit",
            {"file_path": target, "old_string": "    step = 0", "new_string": "    step = 1"},
            iso_at(2),
            sid,
        ),
        claude_snapshot(
            {
                target: {
                    "backupFileName": f"{hashname}@v1",
                    "version": 1,
                    "backupTime": iso_at(2),
                    "realParentDir": proj_root,
                }
            },
            iso_at(2),
            sid,
            "msg_demo_snap_se1",
        ),
        claude_user_toolresult("ok", iso_at(2), sid),
    ]
    history = {
        f"file-history/{sid}/{hashname}@v1": fake_module_source(
            "common", "parse", "step = 0"
        ).encode("utf-8")
    }
    return {
        "sid": sid,
        "source": "claude_code",
        "session_lines": lines,
        "file_history": history,
        "project": {"common.py": fake_module_source("common", "parse", "step = 1").encode("utf-8")},
        "truth": {
            "case_type": "single_edit",
            "source": "claude_code",
            "session_id": sid,
            "expected_rework": [],
            "expected_dup_candidates": [],
            "expected_normal": [{"file": target, "edit_count": 1}],
            "expect_status": "not_rework",
            "also_expect": {},
            "threshold_note": "单次编辑、版本链 = 1（@v1 = 首次编辑前备份）→ 两条判据均不命中",
        },
    }


def build_rework_codex(idx: int, patch_count: int) -> dict:
    """Codex 形态返工：apply_patch 反复 Update 同一文件。

    Codex 侧无 file-history 目录（M1 核对：返工判据以 apply_patch 计数为主）。
    patch_count 恰好 = REWORK_MIN_EDITS → 也算 threshold 语义（应命中，"≥ M"含等于）。
    """
    sid = fake_sid(60 + idx)
    proj_root = FAKE_POSIX_ROOTS[0]
    target = f"{proj_root}/alpha_a.py"
    lines = [codex_meta(sid, iso_at(0), 1)]
    ordinal = 2
    for i in range(1, patch_count + 1):
        lines.append(codex_exec(f"cat {target}", iso_at(2 * i - 1), ordinal, f"call-r{i}-read"))
        ordinal += 1
        lines.append(
            codex_apply_patch([target], [], iso_at(2 * i), ordinal, f"call-r{i}-patch")
        )
        ordinal += 1
    hit = patch_count >= REWORK_MIN_EDITS
    truth = {
        "case_type": "rework" if patch_count > REWORK_MIN_EDITS else "threshold_exact",
        "source": "codex",
        "session_id": sid,
        "expected_rework": (
            [
                {
                    "file": target,
                    "reason": "edits",
                    "min_versions": patch_count,
                    "edit_count": patch_count,
                }
            ]
            if hit
            else []
        ),
        "expected_dup_candidates": [],
        "expected_normal": [],
        "expect_status": "rework_hit" if hit else "not_rework",
        "also_expect": {target: {"edit_count": patch_count}},
        "threshold_note": (
            f"apply_patch 次数恰好 = REWORK_MIN_EDITS（≥ 判据含等于 → 应命中）"
            if patch_count == REWORK_MIN_EDITS
            else f"apply_patch {patch_count} ≥ REWORK_MIN_EDITS → 应命中"
        ),
    }
    return {
        "sid": sid,
        "source": "codex",
        "session_lines": lines,
        "file_history": {},
        "project": {"alpha_a.py": fake_module_source("alpha_a", "compute", f"step = {patch_count}").encode("utf-8")},
        "truth": truth,
    }


def build_normal_codex(idx: int) -> dict:
    sid = fake_sid(70 + idx)
    proj_root = FAKE_POSIX_ROOTS[0]
    target = f"{proj_root}/beta_b.py"
    lines = [
        codex_meta(sid, iso_at(0), 1),
        codex_exec(f"cat {target}", iso_at(1), 2, "call-n1-read"),
        codex_apply_patch([], [target], iso_at(2), 3, "call-n1-add"),
    ]
    content = fake_module_source("beta_b", "render", "mode = 'final'").encode("utf-8")
    return {
        "sid": sid,
        "source": "codex",
        "session_lines": lines,
        "file_history": {},
        "project": {"beta_b.py": content},
        "truth": {
            "case_type": "normal",
            "source": "codex",
            "session_id": sid,
            "expected_rework": [],
            "expected_dup_candidates": [],
            "expected_normal": [{"file": target, "edit_count": 1}],
            "expect_status": "not_rework",
            "also_expect": {},
            "threshold_note": "单次 Add File、无反复覆盖 → 不命中",
        },
    }


# ── case 目录落盘与总装 ──────────────────────────────────────────────────


def materialize(out_root: Path, case: dict, dirname: str) -> None:
    d = out_root / "samples" / dirname
    (d / "file-history" / case["sid"]).mkdir(parents=True, exist_ok=True)
    (d / "project").mkdir(parents=True, exist_ok=True)
    (d / "session.jsonl").write_bytes(("\n".join(case["session_lines"]) + "\n").encode("utf-8"))
    for rel, data in case["file_history"].items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    for rel, data in sorted(case["project"].items()):
        (d / "project" / rel).write_bytes(data)
    (d / "truth.json").write_bytes(
        (json.dumps(case["truth"], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def build_all_cases() -> list:
    """构造全部 case（顺序固定 → 目录名与文件名确定）。"""
    cases = []
    idx = 1
    # rework：Claude 链 N 与 N+1；Codex M+1
    cases.append(build_rework_claude(idx, REWORK_MIN_VERSIONS)); idx += 1
    cases.append(build_rework_claude(idx, REWORK_MIN_VERSIONS + 1)); idx += 1
    cases.append(build_rework_codex(idx, REWORK_MIN_EDITS + 1)); idx += 1
    # duplicate ×2
    cases.append(build_duplicate_claude(idx)); idx += 1
    cases.append(build_duplicate_claude(idx)); idx += 1
    # normal ×2（Claude + Codex）
    cases.append(build_normal_claude(idx)); idx += 1
    cases.append(build_normal_codex(idx)); idx += 1
    # 边界：missing_chain / single_edit / threshold_exact / near_miss
    cases.append(build_missing_chain_claude(idx)); idx += 1
    cases.append(build_single_edit_claude(idx)); idx += 1
    cases.append(build_rework_claude(idx, REWORK_MIN_VERSIONS)); idx += 1
    cases[-1]["truth"]["case_type"] = "threshold_exact"
    cases[-1]["truth"]["threshold_note"] = (
        "版本数恰好 = REWORK_MIN_VERSIONS（≥ 判据含等于 → 应命中）"
    )
    cases.append(build_duplicate_claude(idx, near_miss=True)); idx += 1
    return cases


def case_dirname(case: dict, seq: int) -> str:
    return f"case-{case['source']}-{case['truth']['case_type']}-{seq:02d}"


def generate(out_root: Path) -> dict:
    """生成全部冻结件，返回 manifest dict（两次运行逐字节一致）。"""
    cases = build_all_cases()
    if out_root.exists():
        for p in sorted(out_root.rglob("*"), reverse=True):
            if p.is_file() or p.is_symlink():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    out_root.mkdir(parents=True, exist_ok=True)

    counts = {}
    file_hashes = {}
    seq_by_type = {}
    for case in cases:
        ctype = case["truth"]["case_type"]
        seq_by_type[ctype] = seq_by_type.get(ctype, 0) + 1
        dirname = case_dirname(case, seq_by_type[ctype])
        materialize(out_root, case, dirname)
        counts[ctype] = counts.get(ctype, 0) + 1
        for p in sorted((out_root / "samples" / dirname).rglob("*")):
            if p.is_file():
                rel = p.relative_to(out_root).as_posix()
                file_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    # 互斥断言：同一文件不得同时进 expected_rework 与 expected_normal
    for case in cases:
        rw = {e["file"] for e in case["truth"]["expected_rework"]}
        nm = {e["file"] for e in case["truth"]["expected_normal"]}
        assert not (rw & nm), f"truth 互斥失败: {rw & nm}"

    # 覆盖度门槛校验（数值只在 manifest）
    for t, minc in MIN_COUNT_BY_TYPE.items():
        assert counts.get(t, 0) >= minc, f"覆盖度不足: {t} = {counts.get(t, 0)} < {minc}"

    manifest = {
        "schema": 1,
        "generated_by": "tools/gen_synthetic.py",
        "seed": SEED,
        "determinism": {
            "rng": "splitmix64",
            "stdlib_random": "forbidden",
            "clock_reads": 0,
            "line_endings": "LF",
            "encoding": "utf-8-no-bom",
        },
        "thresholds_source": "agent_rework_lens.config（生成器读 config，不抄数值）",
        "coverage": {
            "min_count_by_type": MIN_COUNT_BY_TYPE,
            "actual_count_by_type": counts,
        },
        "whitelist": {
            "fake_projects": list(FAKE_PROJECTS),
            "fake_users": list(FAKE_USERS),
            "fake_hosts": list(FAKE_HOSTS),
            "fake_session_id_pattern": "00000000-0000-4000-8000-0000000000NN",
            "fake_path_roots": list(FAKE_POSIX_ROOTS),
        },
        "sha256": dict(sorted(file_hashes.items())),
    }
    return manifest


def main(argv: list) -> int:
    _ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="agent-rework-lens 合成 fixtures 生成器")
    ap.add_argument("--check", action="store_true", help="重生成并与现有冻结件逐字节比对")
    args = ap.parse_args(argv)

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp_out = Path(td) / "synthetic"
        manifest = generate(tmp_out)
        tmp_manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")

        if not args.check:
            if MANIFEST_PATH.exists():
                MANIFEST_PATH.unlink()
            for rel in manifest["sha256"]:
                dst = OUT_DIR / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes((tmp_out / rel).read_bytes())
            MANIFEST_PATH.write_bytes(tmp_manifest_bytes)
            print(f"生成完成：{len(manifest['sha256'])} 个文件 → {OUT_DIR}")
            return 0

        # --check：与现有冻结件逐字节比对
        problems = []
        if not MANIFEST_PATH.exists():
            problems.append("缺少 manifest.json（从未生成？）")
        else:
            if MANIFEST_PATH.read_bytes() != tmp_manifest_bytes:
                problems.append("manifest.json 与重生成结果不一致")
            for rel, digest in manifest["sha256"].items():
                dst = OUT_DIR / rel
                if not dst.exists():
                    problems.append(f"缺失冻结件: {rel}")
                    continue
                if hashlib.sha256(dst.read_bytes()).hexdigest() != digest:
                    problems.append(f"sha256 不一致: {rel}")
            for p in sorted(OUT_DIR.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(OUT_DIR).as_posix()
                if rel == "manifest.json" or rel in manifest["sha256"]:
                    continue
                problems.append(f"未登记的现存文件: {rel}")
        if problems:
            print("--check 失败：")
            for pr in problems:
                print(f"  - {pr}")
            return 1
        print(f"--check 通过：{len(manifest['sha256'])} 个冻结件位级一致")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
