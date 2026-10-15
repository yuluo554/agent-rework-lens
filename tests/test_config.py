"""口径单点守门（★ K1）：阈值名的模块级赋值只允许出现在 config.py。"""

import ast
from pathlib import Path

import agent_rework_lens
from agent_rework_lens import config

SRC = Path(agent_rework_lens.__file__).resolve().parent
THRESHOLD_NAMES = ("REWORK_MIN_VERSIONS", "REWORK_MIN_EDITS", "DUP_MATCH_THRESHOLD")


def _assigned_names(node):
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        return []
    names = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Tuple):
            for element in target.elts:
                if isinstance(element, ast.Name):
                    names.append(element.id)
    return names


def test_threshold_names_assigned_only_in_config():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        if relative == "config.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for name in _assigned_names(node):
                if name in THRESHOLD_NAMES:
                    offenders.append("%s:%d:%s" % (relative, node.lineno, name))
    assert offenders == [], "阈值名只允许在 config.py 赋值；命中：%s" % (offenders,)


def test_threshold_values_sane():
    assert isinstance(config.REWORK_MIN_VERSIONS, int) and config.REWORK_MIN_VERSIONS >= 1
    assert isinstance(config.REWORK_MIN_EDITS, int) and config.REWORK_MIN_EDITS >= 1
    assert 0.0 < config.DUP_MATCH_THRESHOLD <= 1.0


def test_definition_sets_frozen_and_disjoint():
    for name in (
        "READ_EVENT_KINDS",
        "WRITE_EVENT_KINDS",
        "SYMBOL_PREFIX_TOKENS",
        "SYMBOL_SUFFIX_TOKENS",
        "SUPPORTED_SYMBOL_LANGUAGES",
    ):
        value = getattr(config, name)
        assert isinstance(value, frozenset) and value, "%s 必须是非空 frozenset" % name
    assert not (config.READ_EVENT_KINDS & config.WRITE_EVENT_KINDS), "读/写口径集合不得重叠"
