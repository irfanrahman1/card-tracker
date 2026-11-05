# One container for the whole app: builds the React website, then runs the
# Python API, which also serves the website. Used by the host (Koyeb) to deploy.

# ---- 1. Build the website ----
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Run the API ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./static

# Don't run as root.
RUN useradd --create-home appuser
USER appuser

# Hosts tell the app which port to use with $PORT (8000 if not set).
# Visitor addresses from the host's proxy are read safely by app/auth.py
# (TRUSTED_PROXY_HOPS), so uvicorn isn't told to trust forwarded headers itself.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
