"""测试公共配置：把 src/ 放入 sys.path（源码态可测；安装态同源，两条通路都被覆盖）。"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
