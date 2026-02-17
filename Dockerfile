# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build --outDir /build/dist

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libchromaprint-tools ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY --from=frontend-build /build/dist ./static/

RUN mkdir -p /data /music

ENV MUSIC_DIR=/music \
    DATABASE_URL=sqlite:////data/autotagger.db \
    LOG_LEVEL=INFO

EXPOSE 8765
VOLUME ["/music", "/data"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
