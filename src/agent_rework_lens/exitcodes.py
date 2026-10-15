"""退出码契约（★ K2，锁进测试；见 plan/04 §3）。

0 成功 / 1 内部错误 / 2 用法错误 / 3 未发现可分析日志。
4（STAGE_NOT_READY，骨架期临时）已于 M2 按 K2 流程退役：删常量 → 改测试 → 改 plan/07 K2
（决策记录 D-M2-1）。若未来需要新语义，使用新的显式异常与退出码，不复用已退役编号。
"""

OK = 0
INTERNAL_ERROR = 1
USAGE_ERROR = 2
NO_SOURCES = 3

ALL_CODES = (OK, INTERNAL_ERROR, USAGE_ERROR, NO_SOURCES)
