FROM python:3.11

# 直接从官方 node:20-slim 镜像复制 Node.js + npm，完全不依赖 apt/NodeSource
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:20-slim /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

ENV USER_DATA_DIR=/data

COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY backend/pyproject.toml backend/uv.lock ./backend/

RUN npm ci --include=dev \
  && npm ci --prefix frontend --include=dev \
  && cd backend && uv sync --frozen

COPY . .

EXPOSE 3000 5001

VOLUME ["/data"]

CMD ["npm", "run", "dev"]
