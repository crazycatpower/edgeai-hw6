#!/usr/bin/env bash
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="/var/lib/edgeai-hw6"
STATE_FILE="${STATE_DIR}/deployed.txt"
HISTORY_FILE="${STATE_FILE}.history"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
POWER_PROFILE="${SCRIPT_DIR}/power_profile.json"

IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "[deploy] Starting deployment of tag: ${IMAGE_TAG}"

# Step 1: Parse power profile and set nvpmodel
POWER_MODE=$(python3 -c "
import json, sys
with open('${POWER_PROFILE}') as f:
    profile = json.load(f)
print(profile.get('production', '15W'))
")
echo "[deploy] Setting nvpmodel to ${POWER_MODE}"

declare -A POWER_IDS=(["MAXN"]="0" ["10W"]="1" ["15W"]="2" ["7W"]="3")
POWER_ID="${POWER_IDS[$POWER_MODE]:-2}"
sudo nvpmodel -m "${POWER_ID}" || echo "[deploy] WARNING: nvpmodel failed, continuing"
sudo jetson_clocks || echo "[deploy] WARNING: jetson_clocks failed, continuing"

# Step 2: Save current tag as previous
mkdir -p "${STATE_DIR}"
if [ -f "${STATE_FILE}" ]; then
    cp "${STATE_FILE}" "${HISTORY_FILE}"
    echo "[deploy] Previous tag: $(cat ${STATE_FILE})"
fi

# Step 3: Pull and restart
export IMAGE_TAG
cd "${SCRIPT_DIR}"
docker compose -f "${COMPOSE_FILE}" pull
docker compose -f "${COMPOSE_FILE}" up -d --force-recreate

# Step 4: Health check
echo "[deploy] Running health check..."
if ! bash "${SCRIPT_DIR}/healthcheck.sh"; then
    echo "[deploy] Health check FAILED — initiating rollback"
    bash "${SCRIPT_DIR}/rollback.sh"
    exit 1
fi

# Step 5: Record new tag
echo "${IMAGE_TAG}" > "${STATE_FILE}"
echo "[deploy] Deployment of ${IMAGE_TAG} successful"
