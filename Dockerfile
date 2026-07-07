FROM python:3.11

# Copy Node.js + npm from official image (no apt/NodeSource dependency)
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:20-slim /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

ENV USER_DATA_DIR=/data
ENV FLASK_DEBUG=False

COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY backend/pyproject.toml backend/uv.lock ./backend/

RUN npm ci --include=dev \
  && npm ci --prefix frontend --include=dev \
  && cd backend && uv sync

COPY . .

# Build frontend into frontend/dist/ (served by Flask in production)
RUN npm run build

EXPOSE 8080

VOLUME ["/data"]

# Healthcheck hits the single gunicorn port
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=6).getcode()==200 else 1)" || exit 1

# 1. Run Alembic migrations (abort on failure — wrong schema is worse than downtime)
# 2. Start gunicorn: 2 workers × 4 threads, 120s timeout for long simulation calls
CMD ["/bin/sh", "-c", "cd /app/backend && uv run alembic upgrade head && exec uv run gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 4 --timeout 120 'app:create_app()'"]
