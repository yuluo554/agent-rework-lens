"""HTML 渲染器（可选形态）——与 Markdown 同渲染源、零外链、可离线打开。

契约（K6/K11）：纯函数、不读时钟；全部样式内联；无 ``http(s)://``、无 ``<script src>``、
无字体/图片外部引用（tests/test_report.py 断言）。
"""

from __future__ import annotations

from html import escape as _html_escape

from .model import DUP_DISCLOSURE, ReportModel

_STYLE = """
:root { color-scheme: light; }
body { font-family: system-ui, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 2rem auto;
       max-width: 60rem; line-height: 1.6; color: #1f2430; padding: 0 1rem; }
h1 { font-size: 1.5rem; border-bottom: 2px solid #1f2430; padding-bottom: .4rem; }
h2 { font-size: 1.15rem; margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0; }
th, td { border: 1px solid #c9d0da; padding: .35rem .6rem; text-align: left; font-size: .95rem; }
th { background: #f2f5f9; }
.meta { color: #4a5568; font-size: .92rem; }
.disclosure { background: #fff8e1; border-left: 4px solid #d69e2e; padding: .5rem .8rem; }
.empty { color: #718096; font-style: italic; }
footer { margin-top: 2.5rem; color: #718096; font-size: .85rem; }
"""


def render_html(model: ReportModel) -> str:
    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head>")
    parts.append('<meta charset="utf-8">')
    parts.append("<title>%s</title>" % _e(model.meta.title))
    parts.append("<style>%s</style>" % _STYLE)
    parts.append("</head>")
    parts.append("<body>")
    parts.append("<h1>%s</h1>" % _e(model.meta.title))
    parts.append(
        '<p class="meta">工具：%s %s ｜ 数据来源：%s ｜ 阈值口径：%s</p>'
        % (
            _e(model.meta.tool_name),
            _e(model.meta.tool_version),
            _e(model.meta.source_summary or "无数据"),
            _e(model.meta.thresholds_note or "见 config.py（单点定义）"),
        )
    )

    parts.append("<h2>返工文件 Top</h2>")
    if model.rework_findings:
        parts.append(
            "<table><thead><tr><th>文件</th><th>判定</th><th>版本数</th><th>Edit 次数</th>"
            "<th>理由</th><th>证据锚点</th></tr></thead><tbody>"
        )
        for item in model.rework_findings:
            parts.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>"
                % (
                    _e(item.file_path),
                    _e(item.verdict),
                    "-" if item.version_count is None else str(item.version_count),
                    item.edit_count,
                    _e("、".join(item.reasons) or "-"),
                    _e("、".join(item.evidence) or "-"),
                )
            )
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="empty">无数据（未启用或未发现达标文件）。</p>')

    parts.append("<h2>重复候选 Top</h2>")
    parts.append('<p class="disclosure">%s</p>' % _e(DUP_DISCLOSURE))
    if model.dup_candidates:
        parts.append(
            "<table><thead><tr><th>新写符号</th><th>已存在符号</th>"
            "<th>命中理由</th><th>证据（会话:锚点）</th></tr></thead><tbody>"
        )
        for cand in model.dup_candidates:
            reason = cand.match_reason
            if cand.similarity is not None:
                reason = "%s（相似度 %.2f）" % (reason, cand.similarity)
            anchor = cand.new_evidence or cand.existing_evidence or "-"
            parts.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (_e(cand.new_symbol), _e(cand.existing_symbol), _e(reason), _e(anchor))
            )
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="empty">无数据（未启用或未发现候选）。</p>')

    parts.append("<h2>会话指标</h2>")
    if model.session_metrics:
        parts.append("<table><thead><tr><th>会话</th><th>Read</th><th>Write/Edit</th><th>Read:Edit 比</th></tr></thead><tbody>")
        for m in model.session_metrics:
            ratio = "未定义（无写操作）" if m.read_edit_ratio is None else "%.2f" % m.read_edit_ratio
            parts.append(
                "<tr><td>%s</td><td>%d</td><td>%d</td><td>%s</td></tr>"
                % (_e(m.session_id), m.reads, m.writes, ratio)
            )
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="empty">无数据。</p>')

    parts.append("<h2>注记</h2>")
    if model.notes:
        parts.append("<ul>")
        for note in model.notes:
            parts.append("<li>%s</li>" % _e(note))
        parts.append("</ul>")
    else:
        parts.append("<p>（无）</p>")

    parts.append("<footer>本报告为纯本地文件：无外链、无遥测、可离线打开。</footer>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


def _e(value: str) -> str:
    return _html_escape(str(value), quote=True)
