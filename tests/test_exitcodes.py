"""退出码契约锁测（★ K2）。"""

from agent_rework_lens import exitcodes as ec


def test_codes_lock_literal_values():
    assert ec.OK == 0
    assert ec.INTERNAL_ERROR == 1
    assert ec.USAGE_ERROR == 2
    assert ec.NO_SOURCES == 3
    assert ec.STAGE_NOT_READY == 4


def test_all_codes_consistent_and_distinct():
    assert tuple(ec.ALL_CODES) == (
        ec.OK,
        ec.INTERNAL_ERROR,
        ec.USAGE_ERROR,
        ec.NO_SOURCES,
        ec.STAGE_NOT_READY,
    )
    assert len(set(ec.ALL_CODES)) == len(ec.ALL_CODES)
