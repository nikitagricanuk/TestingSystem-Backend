#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/testing-system/api/staging"
COMPOSE_FILE="${APP_DIR}/compose.staging.yml"
SERVICE="server"

cd "$APP_DIR"

echo "==> Pulling images"
docker compose -f "$COMPOSE_FILE" pull

echo "==> Starting dependencies (db, redis)"
docker compose -f "$COMPOSE_FILE" up -d db redis

echo "==> Running migrations"
docker compose -f "$COMPOSE_FILE" run --rm migrate

echo "==> Starting application"
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"

echo "==> Waiting for container health"
CID="$(docker compose -f "$COMPOSE_FILE" ps -q "$SERVICE")"

# Wait up to 90s for healthy
DEADLINE=$((SECONDS+90))
while true; do
  STATUS="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$CID" 2>/dev/null || echo "missing")"
  if [[ "$STATUS" == "healthy" ]]; then
    echo "✅ Healthy"
    break
  fi
  if [[ "$STATUS" == "unhealthy" ]]; then
    echo "❌ Unhealthy. Showing last logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=200 "$SERVICE" || true
    exit 1
  fi
  if (( SECONDS > DEADLINE )); then
    echo "❌ Timed out waiting for healthy. Showing last logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=200 "$SERVICE" || true
    exit 1
  fi
  sleep 2
done

echo "==> Cleanup old images (optional)"
docker image prune -f >/dev/null 2>&1 || true

echo "✅ Deploy complete"