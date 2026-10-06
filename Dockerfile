# ---- Stage 1: build the React frontend ---------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
# `npm ci` once package-lock.json is committed; `npm install` works without it.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python API that also serves the built frontend -----------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8000)}/health')"

# Hosting platforms (Render, Railway, Fly) inject $PORT. Every worker runs
# migrations on boot; the Postgres advisory lock makes that safe.
CMD ["sh", "-c", "exec gunicorn --workers 2 --threads 4 --bind 0.0.0.0:${PORT:-8000} --access-logfile - wsgi:app"]
