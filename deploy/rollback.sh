#!/usr/bin/env bash
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="/var/lib/edgeai-hw6"
STATE_FILE="${STATE_DIR}/deployed.txt"
HISTORY_FILE="${STATE_FILE}.history"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

echo "[rollback] Starting rollback..."

if [ ! -f "${HISTORY_FILE}" ]; then
    echo "[rollback] ERROR: No previous deployment history found at ${HISTORY_FILE}"
    exit 1
fi

ROLLBACK_TAG=$(cat "${HISTORY_FILE}")
CURRENT_TAG=$(cat "${STATE_FILE}" 2>/dev/null || echo "unknown")

echo "[rollback] Current tag: ${CURRENT_TAG}"
echo "[rollback] Rolling back to: ${ROLLBACK_TAG}"

# Auto-detect Docker Compose V2 plugin or fall back to standalone V1
if docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "[rollback] ERROR: neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

# Use the locally cached image — the previous version was already pulled during deploy
export IMAGE_TAG="${ROLLBACK_TAG}"
cd "${SCRIPT_DIR}"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d --force-recreate --pull never

# Health check
echo "[rollback] Running health check on rolled-back service..."
if ! bash "${SCRIPT_DIR}/healthcheck.sh"; then
    echo "[rollback] CRITICAL: Rollback also failed. Manual intervention required."
    exit 2
fi

# Update state files
echo "${ROLLBACK_TAG}" > "${STATE_FILE}"
echo "${CURRENT_TAG}" > "${HISTORY_FILE}"

echo "[rollback] Rollback to ${ROLLBACK_TAG} successful"
