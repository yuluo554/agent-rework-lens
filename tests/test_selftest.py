"""自检：健康树上必须全绿；检查项集合稳定。"""

from agent_rework_lens.selftest import STATUSES, run_selftest


def test_selftest_all_checks_report_and_pass_on_healthy_tree():
    result = run_selftest()
    assert result.checks
    assert all(c.status in STATUSES for c in result.checks)
    assert result.ok, "自检 FAIL：%s" % [(c.name, c.detail) for c in result.checks if c.status == "fail"]


def test_selftest_check_names_stable():
    names = [c.name for c in run_selftest().checks]
    assert names == ["版本一致性", "口径存在性（config）", "退出码映射", "编码护栏", "发现探测"]
