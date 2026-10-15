"""阈值与口径的**唯一**定义处（★ K1）。

纪律（plan/07 K1/K12）：
- 数值（N / M / 相似度）只在本文件出现一次；报告、基准、生成器、文档一律引用常量名；
- tests/test_config.py 用 AST 守门：阈值名的**模块级赋值只允许出现在本文件**；
- 初始值为保守默认，**M3 由合成基准校准后定稿**（校准同样是改这一处；变更记决策记录）。
"""

# ── 数值阈值（M3 校准定稿；文档/报告不得手写数值） ─────────────────────────
REWORK_MIN_VERSIONS: int = 3  # 返工判定：同一文件版本链出现 ≥ N 个版本
REWORK_MIN_EDITS: int = 3  # 返工判定：单会话内被 Edit ≥ M 次
DUP_MATCH_THRESHOLD: float = 0.9  # 粗匹配高相似度阈值（difflib ratio ∈ [0, 1]）

# ── 口径定义集合 ────────────────────────────────────────────────────────
READ_EVENT_KINDS = frozenset({"read"})  # Read:Edit 比的分子
WRITE_EVENT_KINDS = frozenset({"edit", "write", "multiedit"})  # 分母
SYMBOL_PREFIX_TOKENS = frozenset(
    {"get", "set", "fetch", "make", "create", "build", "handle", "do", "try"}
)
SYMBOL_SUFFIX_TOKENS = frozenset(
    {"helper", "util", "utils", "fn", "func", "impl", "wrapper"}
)
SUPPORTED_SYMBOL_LANGUAGES = frozenset({"python"})  # 首期仅 Python（其他语言显式未支持）
# 写入文件扩展名 → 符号提取语言（支持集之外 → 上游显式披露跳过，不猜测）
SYMBOL_LANGUAGE_BY_SUFFIX = {".py": "python"}

# ── 路径发现口径（FR-1：显式参数 > 环境变量 > 默认位置） ────────────────
DEFAULT_CLAUDE_HOME = "~/.claude"
DEFAULT_CODEX_HOME = "~/.codex"
ENV_CLAUDE_HOME = "ARL_CLAUDE_HOME"
ENV_CODEX_HOME = "ARL_CODEX_HOME"

# ── 展示口径 ────────────────────────────────────────────────────────────
TOOL_NAME = "agent-rework-lens"
COMMAND_NAME = "arl"
