"""auth 路由挂载防回归测试（2026-10 修复）。

背景：main.py 用 try/except Exception 包裹 auth_router 挂载，依赖缺失时
只打印 warning、应用照常启动——2026 年就是这样「静默死亡」了数月：
8 个 auth 路由整体 404，零用户=零错误报告，无人发现。
本测试让任何未来的挂载失败在 CI 立即暴露。
"""


def test_auth_routes_all_mounted():
    from app.main import app

    # 观测面选 openapi() 而非 app.routes：FastAPI 0.142 的 include_router
    # 不再摊平路由，app.routes 里只有 _IncludedRouter 占位对象；
    # openapi() 走完整分发路径，与线上行为一致。
    paths = set(app.openapi().get("paths", {}))
    expected = {
        "/v1/auth/register",
        "/v1/auth/login",
        "/v1/auth/logout",
        "/v1/auth/refresh",
        "/v1/auth/verify-email",
        "/v1/auth/resend-verification",
        "/v1/auth/request-password-reset",
        "/v1/auth/reset-password",
    }
    missing = sorted(expected - paths)
    assert not missing, f"auth 路由缺失（挂载被 try/except 静默吞掉？）: {missing}"


def test_auth_router_import_is_clean():
    """auth_router 模块必须可独立 import（依赖齐备，不再走 except 分支）。"""
    import app.auth_router as ar

    assert hasattr(ar, "router")
    assert ar.router.prefix == "/v1"
