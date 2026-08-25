import os
import sys

# 把各 Python 包目录注入 sys.path，使 `import redtrip_curator` 等可直接导入
# （仓库未用 pyproject 安装，靠 PYTHONPATH/路径注入）。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _d in ("packages/curator", "packages/gate", "packages/library-client", "packages/tools", "apps/api"):
    _p = os.path.join(ROOT, _d)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
