"""Markdown 渲染器（默认形态）。

契约（K6/K11）：纯函数、不读时钟、只渲染模型；空节显示"无数据"，不得显示假结论。
"""

from __future__ import annotations

from .model import DUP_DISCLOSURE, ReportModel


def render_markdown(model: ReportModel) -> str:
    lines = []
    lines.append("# %s" % model.meta.title)
    lines.append("")
    lines.append("- 工具：%s %s" % (model.meta.tool_name, model.meta.tool_version))
    lines.append("- 数据来源：%s" % (model.meta.source_summary or "无数据"))
    lines.append("- 阈值口径：%s" % (model.meta.thresholds_note or "见 config.py（单点定义）"))
    lines.append("")

    lines.append("## 返工文件 Top")
    lines.append("")
    if model.rework_findings:
        lines.append("| 文件 | 判定 | 版本数 | Edit 次数 | 理由 | 证据锚点 |")
        lines.append("|---|---|---|---|---|---|")
        for item in model.rework_findings:
            lines.append(
                "| %s | %s | %s | %d | %s | %s |"
                % (
                    _esc(item.file_path),
                    _esc(item.verdict),
                    "-" if item.version_count is None else str(item.version_count),
                    item.edit_count,
                    _esc("、".join(item.reasons) or "-"),
                    _esc("、".join(item.evidence) or "-"),
                )
            )
    else:
        lines.append("_无数据（未启用或未发现达标文件）。_")
    lines.append("")

    lines.append("## 重复候选 Top")
    lines.append("")
    lines.append("> %s" % DUP_DISCLOSURE)
    lines.append("")
    if model.dup_candidates:
        lines.append("| 新写符号 | 已存在符号 | 命中理由 | 证据（会话:锚点） |")
        lines.append("|---|---|---|---|")
        for cand in model.dup_candidates:
            reason = cand.match_reason
            if cand.similarity is not None:
                reason = "%s（相似度 %.2f）" % (reason, cand.similarity)
            anchor = cand.new_evidence or cand.existing_evidence or "-"
            lines.append(
                "| %s | %s | %s | %s |"
                % (_esc(cand.new_symbol), _esc(cand.existing_symbol), _esc(reason), _esc(anchor))
            )
    else:
        lines.append("_无数据（未启用或未发现候选）。_")
    lines.append("")

    lines.append("## 会话指标")
    lines.append("")
    if model.session_metrics:
        lines.append("| 会话 | Read | Write/Edit | Read:Edit 比 |")
        lines.append("|---|---|---|---|")
        for m in model.session_metrics:
            ratio = "未定义（无写操作）" if m.read_edit_ratio is None else "%.2f" % m.read_edit_ratio
            lines.append("| %s | %d | %d | %s |" % (_esc(m.session_id), m.reads, m.writes, ratio))
    else:
        lines.append("_无数据。_")
    lines.append("")

    lines.append("## 注记")
    lines.append("")
    if model.notes:
        for note in model.notes:
            lines.append("- %s" % note)
    else:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)


def _esc(value: str) -> str:
    """表格单元格转义：防止 ``|`` 破坏表格结构。"""
    return str(value).replace("|", "\\|")
