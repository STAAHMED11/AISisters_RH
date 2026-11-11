# ---- 1. Next.js UI (standalone server) ----
FROM node:20-slim AS web
WORKDIR /f
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build \
 && cp -r .next/static .next/standalone/.next/static \
 && cp -r public .next/standalone/public

# ---- 2. Runtime: Python (Flask API) + the Node binary for the UI server ----
FROM python:3.11-slim
WORKDIR /app
COPY --from=web /usr/local/bin/node /usr/local/bin/node
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY start.sh start.sh
COPY --from=web /f/.next/standalone web
ENV DATA_DIR=/data PYTHONUNBUFFERED=1 NEXT_TELEMETRY_DISABLED=1
VOLUME /data
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/api/health', timeout=4)"
CMD ["/app/start.sh"]
