"""合成会话基准 runner（M4 实现）。

口径（plan/04 §9）：
- 覆盖率门槛数值**只在下发数据（manifest.json）里**，不在代码里；
- 不达标 → 明确"未达标清单"，退出码 1；"未启用"套件不冒充通过；
- 可证伪探活：注入缺陷 → 基准必须报未达标。
"""

from __future__ import annotations

from ..errors import StageNotReady


def run_bench(data_dir=None):
    raise StageNotReady("合成会话基准", "M4（数据集于 M1 冻结）")
