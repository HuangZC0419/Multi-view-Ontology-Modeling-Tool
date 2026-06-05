# syntax=docker/dockerfile:1

FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.9-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY test.png /app/test.png
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN mkdir -p /app/backend/projects /app/backend/uploads

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
