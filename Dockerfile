# Build the static SPA.
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Run the API and serve the built SPA from the same origin.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JP_DATABASE_URL=sqlite:////data/app.db \
    JP_FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend

COPY backend/pyproject.toml ./
COPY backend/app/ ./app/
COPY backend/alembic.ini ./
COPY backend/alembic/ ./alembic/
RUN pip install --no-cache-dir . \
    && mkdir -p /data \
    && chown 1000:1000 /data \
    && addgroup --system --gid 1000 app \
    && adduser --system --uid 1000 --ingroup app --home /home/app app

COPY --from=frontend-build --chown=1000:1000 /build/frontend/dist /app/frontend/dist
USER 1000:1000
EXPOSE 8010
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=3)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1,172.16.0.0/12"]
