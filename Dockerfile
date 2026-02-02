# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11-slim
FROM mirror.gcr.io/python:${PYTHON_VERSION} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# System deps (build tools optional; keep if you compile wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential git libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Poetry (no venv; we’ll install into system env for simplicity)
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VERSION=2.1.4
RUN curl -sSL https://install.python-poetry.org | python - --version ${POETRY_VERSION} \
 && ln -s ${POETRY_HOME}/bin/poetry /usr/local/bin/poetry

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
