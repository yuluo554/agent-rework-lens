"""报告层：只渲染引擎产出的模型（零判定逻辑、零外链、确定性，K6）。"""

from .model import DUP_DISCLOSURE, ReportMeta, ReportModel
from .markdown import render_markdown
from .html import render_html

__all__ = ["DUP_DISCLOSURE", "ReportMeta", "ReportModel", "render_markdown", "render_html"]
