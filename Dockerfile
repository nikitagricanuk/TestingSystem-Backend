# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11-slim
FROM python:${PYTHON_VERSION} AS base

# ----------------------
# Настройка окружения
# ----------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME=/opt/poetry \
    PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# ----------------------
# Установка системных зависимостей
# ----------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential git libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ----------------------
# Установка Poetry
# ----------------------
ENV POETRY_VERSION=2.1.4
RUN curl -sSL https://install.python-poetry.org | python - --version ${POETRY_VERSION} \
    && ln -s ${POETRY_HOME}/bin/poetry /usr/local/bin/poetry

# ----------------------
# Копирование зависимостей для кеша Docker
# ----------------------
COPY pyproject.toml poetry.lock* ./

# Не устанавливаем корневой пакет, только зависимости
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# ----------------------
# Копирование исходников проекта
# ----------------------
COPY . .

# ----------------------
# Создание безопасного пользователя
# ----------------------
RUN adduser --disabled-password --gecos "" --home "/nonexistent" --shell "/sbin/nologin" --no-create-home appuser
USER appuser

# ----------------------
# Экспонируемый порт
# ----------------------
EXPOSE 8000

# ----------------------
# Команда запуска FastAPI через uvicorn
# ----------------------
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
