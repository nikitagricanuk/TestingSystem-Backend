# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11-slim
FROM mirror.gcr.io/python:${PYTHON_VERSION} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (build tools optional; keep if you compile wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl build-essential git \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Poetry (no venv; we’ll install into system env for simplicity)
ENV POETRY_VERSION=2.1.4
RUN pip install "poetry==${POETRY_VERSION}"

# ---- Copy only dependency files first to leverage Docker cache
COPY pyproject.toml poetry.lock* ./

# IMPORTANT: prevent Poetry from trying to install the root package during deps step
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

# ---- Now copy the rest of your project
COPY . .

# Create non-root user (after files are present so chown is fast if needed)
RUN adduser --disabled-password --gecos "" --home "/nonexistent" --shell "/sbin/nologin" --no-create-home appuser
USER appuser

EXPOSE 8000

# Choose one of the commands below:

# A) Uvicorn directly (simplest). Replace 'your_module.app:app' with your ASGI import path.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# B) Or Gunicorn with Uvicorn workers:
# CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "your_module.app:app", "--bind", "0.0.0.0:8000"]