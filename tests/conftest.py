import os
import sys

# 把各 Python 包目录注入 sys.path，使 `import redtrip_curator` 等可直接导入
# （仓库未用 pyproject 安装，靠 PYTHONPATH/路径注入）。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 测试进程环境止血（2026-10 修复）────────────────────────────
# 背景：apps/api/app/main.py 在 import 时 load_dotenv(ROOT/".env")，
# pytest 单进程下 test_api_degraded（字典序首个 import app.main 的测试）
# 会把生产 .env 的 LLM_MODEL 灌进 os.environ，污染其后所有测试——
# test_llm_provider::test_clear_thread_provider_falls_back 因此假失败
# （断言回落默认值 Qwen-flash，实际读到生产 gpt-4o-mini）。
# 这里在任何测试模块 import 前清空 LLM_*（空串亦可阻止 dotenv 覆盖，
# 因 dotenv 默认 override=False）；生产服务不受影响（systemd 直灌 .env）。
# 注意：LLM_TIMEOUT_S 必须 pop 而非置空串——llm.py:134 是
# float(os.getenv("LLM_TIMEOUT_S", "180"))，空串存在时默认值不生效，float("") 会炸。
for _k in ("LLM_API_BASE", "LLM_API_KEY", "LLM_MODEL"):
    os.environ[_k] = ""
os.environ.pop("LLM_TIMEOUT_S", None)
# ──────────────────────────────────────────────────────────────
for _d in ("packages/curator", "packages/gate", "packages/library-client", "packages/tools", "apps/api"):
    _p = os.path.join(ROOT, _d)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
