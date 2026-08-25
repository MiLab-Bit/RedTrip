# @redtrip/api

FastAPI 薄层。W2 返回 `content/fixtures/demo-route.json`；W3+ 接 library-client / curator。

## 启动

```bat
set PATH=%LOCALAPPDATA%\RedTripToolchain\node;%PATH%
cd RedTrip
python -m venv .venv
.venv\Scripts\pip install -r apps\api\requirements.txt
.venv\Scripts\uvicorn app.main:app --app-dir apps\api --host 127.0.0.1 --port 8787 --reload
```

或使用仓库根目录 `scripts\dev-api.cmd`。

- Health: `GET http://127.0.0.1:8787/v1/health`
- Curate: `POST http://127.0.0.1:8787/v1/curate`
