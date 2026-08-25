# RedTrip 策展后端（FastAPI / Python）
# 注意：本 Dockerfile 的构建上下文（context）必须是 RedTrip 仓库根目录，
# 因为运行入口 app/main.py 通过 parents[3] 定位仓库根，并把 packages/ 注入 sys.path。
FROM python:3.13-slim
WORKDIR /RedTrip/apps/api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

# 仅安装运行依赖；curator / gate / library-client 为纯标准库 Python 包，随源码复制，无需 pip。
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码与同仓 Python 包（保持 RedTrip/apps/api/app 与 RedTrip/packages 的层级）
COPY apps/api/app ./app
COPY packages /RedTrip/packages

EXPOSE 8799
# 需要环境变量：SLC_API_KEY / LLM_API_KEY / LLM_API_BASE / LLM_MODEL / LLM_TIMEOUT_S / REDTRIP_MODE / API_PORT
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8799/v1/health', timeout=3); sys.exit(0)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8799"]
