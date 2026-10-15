"""退出码契约（★ K2，锁进测试；见 plan/04 §3）。

0 成功 / 1 内部错误 / 2 用法错误 / 3 未发现可分析日志 / 4 阶段未就绪（骨架期临时，M2 起退役）。
退役时：删常量 → 改 tests/test_cli.py → 更新 plan/07 K2。
"""

OK = 0
INTERNAL_ERROR = 1
USAGE_ERROR = 2
NO_SOURCES = 3
STAGE_NOT_READY = 4

ALL_CODES = (OK, INTERNAL_ERROR, USAGE_ERROR, NO_SOURCES, STAGE_NOT_READY)
