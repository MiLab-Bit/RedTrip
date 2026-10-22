"""RedTrip API 路由模块。

按域拆自原 apps/api/app/main.py（1259 行上帝路由）。每个子模块持有一个
APIRouter，仅声明路由处理器；共享的引擎、缓存、Pydantic 模型、任务状态
仍留在 app.main，避免重复定义与循环依赖。main.py 在末尾 include 这些路由。
"""
