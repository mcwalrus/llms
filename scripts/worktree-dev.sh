#!/usr/bin/env bash
set -e

# Worktree-aware LLMS dev harness
# Usage: ./scripts/worktree-dev.sh <worktree_dir>

WORKTREE_DIR="${1:-$(pwd)}"
DIRNAME=$(basename "$WORKTREE_DIR")
CONTAINER_NAME="llms-wt-${DIRNAME}"

# Find a free port based on directory hash
PORT_BASE=40000
DIR_HASH=$(echo -n "$DIRNAME" | cksum | awk '{print $1}')
PORT=$((PORT_BASE + (DIR_HASH % 10000)))

# Check if port is free, increment until found
while nc -z 127.0.0.1 "$PORT" 2>/dev/null; do
  PORT=$((PORT + 1))
done

echo "Starting LLMS worktree container: $CONTAINER_NAME on port $PORT"

docker run -d --rm \
  --name "$CONTAINER_NAME" \
  -p "${PORT}:3000" \
  -v "${WORKTREE_DIR}/config.json:/app/config.json:ro" \
  -e PORT=3000 \
  -e HOST=0.0.0.0 \
  -e NODE_ENV=development \
  llms:dev

# Wait for healthcheck
for i in {1..30}; do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    echo "Container healthy on port $PORT"
    echo "PORT=$PORT"
    echo "CONTAINER=$CONTAINER_NAME"
    exit 0
  fi
  sleep 1
done

echo "Container failed to start" >&2
docker logs "$CONTAINER_NAME" >&2
docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
exit 1
