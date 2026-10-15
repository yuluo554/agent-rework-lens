"""基准套件：合成会话评测（数据于 M1 冻结；runner 于 M4 实现）。"""

from .runner import run_bench

__all__ = ["run_bench"]
