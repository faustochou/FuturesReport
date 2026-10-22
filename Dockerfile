# ---------------------------------------------------------------------------
# Stage 1 - build the frontend (Vue + Vite) into static files.
# The final image has no Node.js: production serves frontend/dist from Flask.
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-build

WORKDIR /app

# vite.config.js aliases @locales to ../locales, so both folders are needed
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --include=dev

COPY frontend ./frontend
COPY locales ./locales
RUN cd frontend && npm run build


# ---------------------------------------------------------------------------
# Stage 2 - backend runtime (Flask API + the built frontend)
# ---------------------------------------------------------------------------
FROM python:3.11

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

ENV USER_DATA_DIR=/data \
    FLASK_DEBUG=false \
    PYTHONUNBUFFERED=1 \
    UV_HTTP_TIMEOUT=600 \
    UV_CONCURRENT_DOWNLOADS=4

# torch / CUDA 轮子体积很大，uv 默认 30 秒的 HTTP 逾时在较慢的网络上会下载失败，
# 所以上面把 UV_HTTP_TIMEOUT 调高并降低并行下载数。
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync

COPY . .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 5001

VOLUME ["/data"]

# 容器编排 / K8s 探针：轻量 healthcheck（使用 stdlib，避免依賴 curl）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys,os; p=os.environ.get('BACKEND_PORT','5001'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health',timeout=6).getcode()==200 else 1)" || exit 1

# Run Alembic migrations first, then start the application (Flask serves the API and the built frontend on 5001).
# Using && so startup aborts if migrations fail (prevents running with wrong schema).
# exec replaces sh with the Python process so SIGTERM from Docker/Coolify reaches it directly.
CMD ["/bin/sh", "-c", "cd /app/backend && uv run alembic upgrade head && exec uv run python run.py"]
