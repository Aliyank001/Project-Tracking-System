FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build -- --base=/static/

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.production
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY backend/ ./
COPY --from=frontend /build/dist /app/frontend/dist
RUN useradd --system --no-create-home projecttrack \
    && mkdir /app/backend/staticfiles \
    && chown projecttrack /app/backend/staticfiles
USER projecttrack
EXPOSE 10000
CMD ["sh", "start-production.sh"]
