"""``python -m agent_rework_lens`` 入口（与 ``arl`` 命令等价，K8）。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
