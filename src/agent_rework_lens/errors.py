"""项目内共享异常类型。"""

from __future__ import annotations


class ArlError(Exception):
    """本项目所有显式错误的基类。"""


class NoSourcesFound(ArlError):
    """未发现可分析日志源。

    CLI 以退出码 3（NO_SOURCES）明确提示，绝不产出伪造空报告。
    """

    def __init__(self, detail: str = ""):
        super().__init__(detail)
        self.detail = detail


class StageNotReady(ArlError):
    """功能未到对应里程碑（骨架期护栏）。

    CLI 以退出码 4（STAGE_NOT_READY）明确拦截——"未就绪"不得伪装成"无发现"。
    未核对字段不得进入指标计算路径（K7），因此解析层在 M1 核对完成前保持拦截。
    """

    def __init__(self, feature: str, ready_at: str):
        super().__init__(f"{feature} 未就绪（计划于 {ready_at} 启用）")
        self.feature = feature
        self.ready_at = ready_at
