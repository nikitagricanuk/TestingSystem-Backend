#!/usr/bin/env sh
set -e

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  max_retries="${MIGRATION_MAX_RETRIES:-10}"
  retry_delay="${MIGRATION_RETRY_DELAY:-2}"
  attempt=1
  while :; do
    if alembic upgrade head; then
      break
    fi
    if [ "$attempt" -ge "$max_retries" ]; then
      echo "Migrations failed after ${attempt} attempts." >&2
      exit 1
    fi
    echo "Migration failed, retrying in ${retry_delay}s... (${attempt}/${max_retries})" >&2
    attempt=$((attempt + 1))
    sleep "$retry_delay"
  done
fi

exec "$@"
