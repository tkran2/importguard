FROM node:24-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv
WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY importguard/ ./importguard/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY --from=frontend /frontend/dist ./frontend/dist/

RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8080

CMD ["uvicorn", "importguard.serve:app", "--host", "0.0.0.0", "--port", "8080"]
