#!/usr/bin/env bash
set -e

# Stop a worktree LLMS container
# Usage: ./scripts/worktree-stop.sh <container_name_or_worktree_dir>

TARGET="${1:-$(basename $(pwd))}"

if docker ps -q --filter "name=$TARGET" | grep -q .; then
  echo "Stopping container: $TARGET"
  docker stop "$TARGET"
  echo "Stopped."
else
  # Try container name from worktree dir
  CONTAINER_NAME="llms-wt-${TARGET}"
  if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
    echo "Stopping container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME"
    echo "Stopped."
  else
    echo "No running container found for: $TARGET"
    exit 1
  fi
fi
